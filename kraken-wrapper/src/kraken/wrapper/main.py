from __future__ import annotations

import argparse
import getpass
import logging
import os
import shlex
import sys
import time
from pathlib import Path
from textwrap import indent
from typing import NamedTuple, NoReturn

from deprecated import deprecated

from kraken.common import (
    AsciiTable,
    BuildscriptMetadata,
    EnvironmentType,
    GitAwareProjectFinder,
    LoggingOptions,
    RequirementSpec,
    TomlConfigFile,
    colored,
    datetime_to_iso8601,
    inline_text,
)
from kraken.common.exceptions import exit_on_known_exceptions

from . import __version__
from ._config import DEFAULT_CONFIG_PATH, AuthModel
from ._option_sets import AuthOptions, EnvOptions
from .venv_manager import Lockfile, VirtualEnvError, VirtualEnvManager

BUILDENV_PATH = Path("build/.kraken/venv")
BUILDSCRIPT_FILENAME = ".kraken.py"
BUILD_SUPPORT_DIRECTORY = "build-support"
LOCK_FILENAME = ".kraken.lock"
_FormatterClass = lambda prog: argparse.RawTextHelpFormatter(prog, max_help_position=60, width=120)  # noqa: E731
logger = logging.getLogger(__name__)


def _get_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        "krakenw",
        formatter_class=_FormatterClass,
        description=inline_text(
            f"""
            This is kraken-wrapper v{__version__}.

            {colored("krakenw", attrs=["bold"])} is a thin wrapper around the {colored("kraken", attrs=["bold"])} cli
            that executes builds in an isolated \\
            build environment. This ensures that builds are reproducible (especially when using \\
            lock files).

            To learn more about kraken, visit https://github.com/kraken-build/kraken-core.
            """
        ),
        epilog=inline_text(
            colored(
                "This is kraken-wrapper's help. To show kraken's help instead, run krakenw -- --help",
                "yellow",
                attrs=["bold"],
            )
        ),
    )
    parser.add_argument("-V", "--version", version=__version__, action="version")
    LoggingOptions.add_to_parser(parser, default_verbosity=1)
    EnvOptions.add_to_parser(parser)

    # NOTE (@NiklasRosenstein): If we combine "+" with remainder, we get options passed after the `cmd`
    #       passed directly into `args` without argparse treating it like an option. This is not the case
    #       when using `nargs=1` for `cmd`.
    parser.add_argument("cmd", nargs="*", metavar="cmd", help="{auth,list-pythons,lock} or a kraken command")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="additional arguments")
    return parser


def _get_lock_argument_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog,
        formatter_class=_FormatterClass,
        description=inline_text(
            f"""
            Rewrite the lock file ({colored(LOCK_FILENAME, attrs=["bold"])}) from the current build environment.
            """
        ),
    )

    return parser


def lock(prog: str, argv: list[str], manager: VirtualEnvManager, project: Project) -> NoReturn:
    parser = _get_lock_argument_parser(prog)
    parser.parse_args(argv)

    if not manager.exists():
        logger.error("cannot lock without a build environment")
        sys.exit(1)

    lockfile = manager.get_lockfile(project.requirements)

    had_lockfile = project.lockfile_path.exists()
    lockfile.write_to(project.lockfile_path)
    manager.set_locked(lockfile)

    logger.info("Lock file %s (%s)", "updated" if had_lockfile else "created", os.path.relpath(project.lockfile_path))
    sys.exit(0)


def _get_auth_argument_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog,
        formatter_class=_FormatterClass,
        description=inline_text(
            """
            Configure the credentials to use when accessing PyPI packages from the given host.
            The password will be stored in the system keychain.
            """
        ),
    )
    AuthOptions.add_to_parser(parser)
    return parser


@deprecated(reason="krakenw config command has been removed in v0.45.0")
def config_main(prog: str, argv: list[str]) -> NoReturn:
    """Deprecated. Do not use."""

    parser = argparse.ArgumentParser(prog=prog, description="deprecated, do not use.")
    parser.add_argument(
        "--installer",
        choices=[x.name for x in EnvironmentType if x.is_wrapped()],
        help="deprecated, has no effect.",
    )
    args = parser.parse_args(argv)

    if args.installer is not None:
        logger.warning("The `krakenw config` command is deprecated and will be removed in a future version.")
        sys.exit(0)

    parser.print_usage()
    sys.exit(1)


def auth(prog: str, argv: list[str], use_keyring_if_available: bool) -> NoReturn:
    config = TomlConfigFile(DEFAULT_CONFIG_PATH)
    auth = AuthModel(config, DEFAULT_CONFIG_PATH, use_keyring_if_available=use_keyring_if_available)
    parser = _get_auth_argument_parser(prog)
    args = AuthOptions.collect(parser.parse_args(argv))

    if args.host and (":" in args.host or "/" in args.host):
        parser.error(f"invalid host name: {args.host}")
    if args.password and args.password_stdin:
        parser.error("cannot use -p,--password and --password-stdin concurrently")

    if args.remove:
        if args.list or args.username or args.password or args.password_stdin:
            parser.error("incompatible arguments")
        if not args.host:
            parser.error("missing argument `host`")
        auth.delete_credentials(args.host)
        config.save()
    elif args.list:
        if args.remove or args.host or args.username or args.password or args.password_stdin:
            parser.error("incompatible arguments")
        table = AsciiTable()
        table.headers = ["Host", "Username", "Password", "Auth check"]
        for host, username, password in auth.list_credentials():
            # Auth check
            check_result = auth_check(auth, args, host, username, password)

            table.rows.append((host, username, password if args.no_mask else "[MASKED]", check_result))
        if table.rows:
            table.print()
    elif args.username:
        if args.password_stdin:
            password = sys.stdin.readline().strip()
            if not password:
                parser.error("no password provided via stdin")
        elif args.password:
            password = args.password
        else:
            password = getpass.getpass(f"Password for {args.host}: ")
        auth.set_credentials(args.host, args.username, password)
        config.save()
    else:
        parser.print_usage()
        sys.exit(1)

    sys.exit(0)


def auth_check(auth: AuthModel, args: AuthOptions, host: str, username: str, password: str) -> str:
    check_result = "[SKIPPED]"  # Default

    if not args.no_check:
        # Check the credential now, aiming to return either OK or FAILED, and print warnings as needed

        credential_result = auth.check_credential(host, username, password)
        if credential_result:
            check_result = "[OK]" if credential_result.auth_check_result else "[FAILED]"

            # If there are any hints, output them to the logger as a warning
            if credential_result.hint:
                logger.warning(host + ": " + credential_result.hint)

            # If verbose, also display the CURL command that people can use plus the first part of the response
            if args.verbose:
                logger.info("Checking auth for host %s with command: %s", host, credential_result.curl_command)
                logger.info(
                    "First 10 lines of response (limited to 1000 chars): %s",
                    ("\n".join(credential_result.raw_result.split("\n")[0:10])[0:1000]),
                )

    return check_result


def list_pythons(prog: str, argv: list[str]) -> NoReturn:
    from kraken.common import findpython

    if argv:
        logger.error(f"{prog}: unexpected arguments")
        sys.exit(1)

    interpreters = findpython.evaluate_candidates(findpython.get_candidates(), findpython.InterpreterVersionCache())
    findpython.print_interpreters(interpreters)
    sys.exit(0)


def _print_env_status(manager: VirtualEnvManager, project: Project) -> None:
    """Print the status of the environment as a nicely formatted table."""

    hash_algorithm = manager.get_hash_algorithm()

    table = AsciiTable()

    table.headers = ["Key", "Source", "Value"]
    rows: list[tuple[str, str, str]] = table.rows  # type: ignore[assignment]  # Upcast

    rows.append(("Requirements", str(project.requirements_path), project.requirements.to_hash(hash_algorithm)))
    if project.lockfile:
        rows.append(("Lockfile", str(project.lockfile_path), "-"))
        rows.append(("  Requirements hash", "", project.lockfile.requirements.to_hash(hash_algorithm)))
        rows.append(("  Pinned hash", "", project.lockfile.to_pinned_requirement_spec().to_hash(hash_algorithm)))
    else:
        rows.append(("Lockfile", str(project.lockfile_path), "n/a"))
    if manager.exists():
        metadata = manager.get_metadata()
        rows.append(("Environment", str(manager._path), ""))
        rows.append(("  Metadata", str(manager.get_metadata_file()), "-"))
        rows.append(("    Created at", "", datetime_to_iso8601(metadata.created_at)))
        rows.append(("    Requirements hash", "", metadata.requirements_hash))
    else:
        rows.append(("Environment", str(manager._path), "n/a"))
    table.print()


def _ensure_installed(
    manager: VirtualEnvManager,
    project: Project,
    reinstall: bool,
    upgrade: bool,
) -> None:
    exists = manager.exists()
    install = reinstall or upgrade or not exists

    operation: str
    reason: str | None = None

    if not exists:
        operation = "Initializing"
    elif upgrade:
        operation = "Upgrading"
    elif reinstall:
        operation = "Reinstalling"
    else:
        operation = "Reusing"

    if not install and exists:
        metadata = manager.get_metadata()
        if project.lockfile and metadata.requirements_hash != project.lockfile.to_pinned_requirement_spec().to_hash(
            metadata.hash_algorithm
        ):
            install = True
            operation = "Re-initializing"
            reason = "outdated compared to lockfile"
        if not project.lockfile and metadata.requirements_hash != project.requirements.to_hash(metadata.hash_algorithm):
            install = True
            operation = "Re-initializing"
            reason = "outdated compared to requirements"

    if install:
        if not project.lockfile or upgrade:
            source_name = "requirements"
            source = project.requirements
            source_file = project.requirements_path
        else:
            source_name = "lock file"
            source = project.lockfile.to_pinned_requirement_spec()
            source_file = project.lockfile_path

        logger.info(
            "%s build environment from %s (%s)%s.",
            operation,
            source_name,
            os.path.relpath(source_file),
            f" ({reason})" if reason else "",
        )

        tstart = time.perf_counter()
        manager.install(source, reinstall)
        duration = time.perf_counter() - tstart
        logger.info("Operation complete after %.3fs.", duration)

    else:
        logger.info("%s build environment", operation)


class Project(NamedTuple):
    directory: Path
    requirements_path: Path
    requirements: RequirementSpec
    lockfile_path: Path
    lockfile: Lockfile | None


def load_project(directory: Path, outdated_check: bool = True) -> Project:
    """
    This method loads the details about the current Kraken project from the current working directory
    and returns it. The project information includes the requirements for the project as well as the
    parsed lockfile, if present.

    We use the :class:`GitAwareProjectFinder` in its :func:`default <GitAwareProjectFinder.default>`
    configuration to determine the root directory of the Kraken project. This is later used to add the
    ``-p, --project-dir`` option when invoking the project's underlying Kraken installation, as well as
    adding to relative task and project selectors.

    For example, in the following project:

    .. code-block::

        /
            .git/
            .kraken.py
            examples/           << cwd
                .kraken.py
            src/

    Running ``krakenw run test-examples`` will translate into ``kraken run -p .. examples:test-examples``
    due to the :class:`GitAwareProjectFinder` finding ``/`` as the Kraken project root.

    Note that if the ``examples/`` wanted to be its own Kraken project, independent of the project at ``//``,
    you can add a line spelling ``# ::krakenw-root`` to the ``.kraken.py`` file. In that case, the
    :class:`GitAwareProjectFinder` will consider that directory the root Kraken project (assuming your CWD
    is somewhere within it).

    :param directory: The directory for which to load the build project details for.
    :param outdated_check: If enabled, performs a check to see if the requirements that the lockfile was
        generated with is outdated compared to the project requirements.
    """

    project_info = GitAwareProjectFinder.default().find_project(directory)
    if not project_info:
        logger.error("no buildscript")
        sys.exit(1)
    script, runner = project_info

    # Load requirement spec from build script.
    logger.debug('Loading requirements from "%s" (runner: %s)', script, runner)

    # Extract the metadata provided by the buildscript() function call at the top of the build script.
    if not runner.has_buildscript_call(script):
        metadata = BuildscriptMetadata(requirements=["kraken-core"])
        logger.error(
            "Kraken build scripts must call the `buildscript()` function to be compatible with Kraken wrapper. "
            "Please add something like this at the top of your build script:\n\n%s\n"
            % indent(runner.get_buildscript_call_recommendation(metadata), "    "),
        )
        sys.exit(1)

    with BuildscriptMetadata.capture() as future:
        runner.execute_script(script, {})
    assert future.done()
    requirements = RequirementSpec.from_metadata(future.result())

    # Load lockfile if it exists.
    lockfile_path = script.with_suffix(".lock")
    if lockfile_path.is_file():
        logger.debug('loading lockfile from "%s"', lockfile_path)
        lockfile = Lockfile.from_path(lockfile_path)
        if outdated_check and lockfile and lockfile.requirements != requirements:
            logger.warning(
                'Lock file "%s" is outdated compared to requirements in "%s". Consider updating the lock file with '
                '"krakenw --upgrade lock"',
                os.path.relpath(lockfile_path),
                os.path.relpath(script),
            )
    else:
        lockfile = None

    return Project(script.parent, script, requirements, lockfile_path, lockfile)


@exit_on_known_exceptions(VirtualEnvError, exit_code=2)
def main(krakenw_args: list[str] | None = None) -> NoReturn:
    parser = _get_argument_parser()
    args = parser.parse_args(args=krakenw_args)
    logging_options = LoggingOptions.collect(args)
    logging_options.init_logging()
    env_options = EnvOptions.collect(args)

    if not args.cmd and not env_options.any():
        parser.print_usage()
        sys.exit(0)

    # When we delegate to the Kraken CLI, we want to make sure it can detect that it has been invoked from the wrapper.
    os.environ["KRAKENW"] = "1"

    # Convert the arguments we defined in the argument parser to the actual subcommand that we want
    # delegated.
    cmd: str | None = args.cmd[0] if args.cmd else None
    argv: list[str] = args.cmd[1:] + args.args

    if cmd in ("a", "auth"):
        # The `auth` command does not require any current project information, it can be used globally.
        auth(f"{parser.prog} auth", argv, use_keyring_if_available=not env_options.no_keyring)

    if cmd in ("config",):
        config_main(f"{parser.prog} config", argv)

    if cmd in ("list-pythons",):
        list_pythons(f"{parser.prog} list-pythons", argv)

    # The project details and build environment manager are relevant for any command that we are delegating.
    # This includes the built-in `lock` command.
    config_file = TomlConfigFile(DEFAULT_CONFIG_PATH)
    project = load_project(Path.cwd(), outdated_check=not env_options.upgrade)
    manager = VirtualEnvManager(
        project.directory,
        project.directory / BUILDENV_PATH,
        AuthModel(config_file, DEFAULT_CONFIG_PATH, use_keyring_if_available=not env_options.no_keyring),
    )

    # Execute environment operations before delegating the command.

    is_lock_command = cmd in ("lock", "l")

    if env_options.status:
        if cmd or argv:
            logger.error("--status option must be used alone")
            sys.exit(1)
        _print_env_status(manager, project)
        sys.exit(0)

    if env_options.uninstall:
        if cmd or argv:
            logger.error("--uninstall option must be used alone")
            sys.exit(1)
        manager.remove()
        sys.exit(0)
    if env_options.any() or not is_lock_command:
        _ensure_installed(
            manager,
            project,
            env_options.reinstall,
            env_options.upgrade,
        )

    if cmd is None:
        assert not argv
        sys.exit(0)

    elif cmd in ("l", "lock"):
        lock(f"{parser.prog} lock", argv, manager, project)

    else:
        if project.directory.absolute() != Path.cwd():
            argv += ["-p", str(project.directory)]
        command = [cmd, *argv]
        logger.info("$ %s", " ".join(map(shlex.quote, ["kraken"] + command)))
        manager.dispatch_to_kraken_cli(command)


if __name__ == "__main__":
    main()
