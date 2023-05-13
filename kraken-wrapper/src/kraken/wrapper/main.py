from __future__ import annotations

import argparse
import builtins
import getpass
import logging
import os
import shlex
import sys
import time
from functools import partial
from pathlib import Path
from textwrap import indent
from typing import NamedTuple, NoReturn

from kraken.common import (
    AsciiTable,
    BuildscriptMetadata,
    EnvironmentType,
    GitAwareProjectFinder,
    LoggingOptions,
    RequirementSpec,
    TomlConfigFile,
    datetime_to_iso8601,
    deprecated_get_requirement_spec_from_file_header,
    inline_text,
)
from termcolor import colored

from . import __version__
from ._buildenv_manager import BuildEnvManager
from ._config import DEFAULT_CONFIG_PATH, AuthModel
from ._lockfile import Lockfile, calculate_lockfile
from ._option_sets import AuthOptions, EnvOptions

BUILDENV_PATH = Path("build/.kraken/venv")
BUILDSCRIPT_FILENAME = ".kraken.py"
BUILD_SUPPORT_DIRECTORY = "build-support"
DEFAULT_INTERPRETER_CONSTRAINT = ">=3.7"
LOCK_FILENAME = ".kraken.lock"
_FormatterClass = lambda prog: argparse.RawTextHelpFormatter(prog, max_help_position=60, width=120)  # noqa: 731
logger = logging.getLogger(__name__)
print = partial(builtins.print, "[krakenw]", flush=True)
eprint = partial(print, file=sys.stderr)


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
    LoggingOptions.add_to_parser(parser)
    EnvOptions.add_to_parser(parser)

    # NOTE (@NiklasRosenstein): If we combine "+" with remainder, we get options passed after the `cmd`
    #       passed directly into `args` without argparse treating it like an option. This is not the case
    #       when using `nargs=1` for `cmd`.
    parser.add_argument("cmd", nargs="*", metavar="cmd", help="{a,auth,lock,l} or a kraken command")
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


def lock(prog: str, argv: list[str], manager: BuildEnvManager, project: Project) -> NoReturn:
    parser = _get_lock_argument_parser(prog)
    parser.parse_args(argv)

    if not manager.exists():
        print("error: cannot lock without a build environment")
        sys.exit(1)

    environment = manager.get_environment()
    distributions = environment.get_installed_distributions()
    lockfile, extra_distributions = calculate_lockfile(project.requirements, distributions)

    if environment.get_type() == EnvironmentType.VENV:
        extra_distributions.discard("pip")  # We'll always have that in a virtual env.

    if extra_distributions:
        eprint("found extra distributions in build enviroment:", ", ".join(extra_distributions))

    had_lockfile = project.lockfile_path.exists()
    lockfile.write_to(project.lockfile_path)
    manager.set_locked(lockfile)

    eprint("lock file", "updated" if had_lockfile else "created", f"({project.lockfile_path})")
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


def auth(prog: str, argv: list[str]) -> NoReturn:
    config = TomlConfigFile(DEFAULT_CONFIG_PATH)
    auth = AuthModel(config, DEFAULT_CONFIG_PATH)
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
        table.headers = ["Host", "Username", "Password"]
        for host, username, password in auth.list_credentials():
            table.rows.append((host, username, password))
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
            password = getpass.getpass(f"Password for {args.host}:")
        auth.set_credentials(args.host, args.username, password)
        config.save()
    else:
        parser.print_usage()
        sys.exit(1)

    sys.exit(0)


def _print_env_status(manager: BuildEnvManager, project: Project) -> None:
    """Print the status of the environent as a nicely formatted table."""

    hash_algorithm = manager.get_hash_algorithm()

    table = AsciiTable()
    table.headers = ["Key", "Source", "Value"]
    table.rows.append(("Requirements", str(project.requirements_path), project.requirements.to_hash(hash_algorithm)))
    if project.lockfile:
        table.rows.append(("Lockfile", str(project.lockfile_path), "-"))
        table.rows.append(("  Requirements hash", "", project.lockfile.requirements.to_hash(hash_algorithm)))
        table.rows.append(("  Pinned hash", "", project.lockfile.to_pinned_requirement_spec().to_hash(hash_algorithm)))
    else:
        table.rows.append(("Lockfile", str(project.lockfile_path), "n/a"))
    if manager.exists():
        metadata = manager.get_metadata()
        environment = manager.get_environment()
        table.rows.append(("Environment", str(environment.get_path()), environment.get_type().name))
        table.rows.append(("  Metadata", str(manager.get_metadata_file()), "-"))
        table.rows.append(("    Created at", "", datetime_to_iso8601(metadata.created_at)))
        table.rows.append(("    Requirements hash", "", metadata.requirements_hash))
    else:
        table.rows.append(("Environment", str(manager.get_environment().get_path()), "n/a"))
    table.print()


def _ensure_installed(
    manager: BuildEnvManager,
    project: Project,
    reinstall: bool,
    upgrade: bool,
    env_type: EnvironmentType | None = None,
) -> None:
    exists = manager.exists()
    install = reinstall or upgrade or not exists

    operation: str
    reason: str | None = None

    if not exists:
        env_type = env_type or env_type or manager.get_environment().get_type()
        operation = "initializing"
    elif upgrade:
        operation = "upgrading"
    elif reinstall:
        operation = "reinstalling"
    else:
        operation = "reusing"

    current_type = manager.get_environment().get_type()
    if env_type is not None:
        type_changed = exists and env_type != current_type
        if not install and type_changed:
            install = True
            manager.remove()
            operation = "re-initializing"
            reason = f"type changed from {current_type.name}"
        elif install and type_changed:
            reason = f"type changed from {current_type.name}"

    if not install and exists:
        metadata = manager.get_metadata()
        if project.lockfile and metadata.requirements_hash != project.lockfile.to_pinned_requirement_spec().to_hash(
            metadata.hash_algorithm
        ):
            install = True
            operation = "re-initializing"
            reason = "outdated compared to lockfile"
        if not project.lockfile and metadata.requirements_hash != project.requirements.to_hash(metadata.hash_algorithm):
            install = True
            operation = "re-initializing"
            reason = "outdated compared to requirements"

    if install:
        if not project.lockfile or upgrade:
            source_name = "requirements"
            source = project.requirements
            transitive = True
        else:
            source_name = "lock file"
            source = project.lockfile.to_pinned_requirement_spec()
            transitive = False

        env_type = env_type or manager.get_environment().get_type()
        eprint(
            operation,
            "build environment of type",
            env_type.name,
            "from",
            source_name,
            f"({reason})" if reason else "",
        )

        tstart = time.perf_counter()
        manager.install(source, env_type, transitive)
        duration = time.perf_counter() - tstart
        eprint(f"operation complete after {duration:.3f}s")

    else:
        eprint(operation, "build environment of type", current_type.name)


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

    :param directory: The directory for which to load the build project details for.
    :param outdated_check: If enabled, performs a check to see if the requirements that the lockfile was
        generated with is outdated compared to the project requirements.
    """

    project_info = GitAwareProjectFinder.default().find_project(directory)
    if not project_info:
        eprint("error: no buildscript")
        sys.exit(1)
    script, runner = project_info

    # Load requirement spec from build script.
    logger.debug('loading requirements from "%s" (runner: %s)', script, runner)

    # For backwards compatibility, support loading the requirements from the comment header.
    requirements = deprecated_get_requirement_spec_from_file_header(script)
    if requirements is not None:
        eprint(
            "error: The # ::requirements header is deprecated and support for it will be removed in a future version "
            "of kraken-wrapper. Please use the `buildscript()` function from the `kraken.common` package "
            "from now on.\n\n%s\n"
            % indent(runner.get_buildscript_call_recommendation(requirements.to_metadata()), "    "),
        )

    # Otherwise, extract the relevant data from the buildscript() call instead.
    else:
        if not runner.has_buildscript_call(script):
            metadata = BuildscriptMetadata(requirements=["kraken-core"])
            eprint(
                "Kraken build scripts must call the `buildscript()` function to be compatible with Kraken wrapper. "
                "Please add something like this at the top of your build script:\n\n%s\n"
                % indent(runner.get_buildscript_call_recommendation(metadata), "    "),
            )
            sys.exit(1)

        with BuildscriptMetadata.capture() as future:
            runner.execute_script(script, {})
        assert future.done()
        requirements = RequirementSpec.from_metadata(future.result())

    # Derive the lockfile path.
    lockfile_path = script.with_suffix(".lock")

    # Load lockfile if it exists.
    if lockfile_path.is_file():
        logger.debug('loading lockfile from "%s"', lockfile_path)
        lockfile = Lockfile.from_path(lockfile_path)
        if outdated_check and lockfile and lockfile.requirements != requirements:
            eprint(f'lock file "{lockfile_path}" is outdated compared to requirements in "{script}"')
            eprint("consider updating the lock file with `krakenw --upgrade lock`")
    else:
        lockfile = None

    return Project(script.parent, script, requirements, lockfile_path, lockfile)


def main() -> NoReturn:
    parser = _get_argument_parser()
    args = parser.parse_args()
    logging_options = LoggingOptions.collect(args)
    logging_options.init_logging()
    env_options = EnvOptions.collect(args)

    if not args.cmd and not env_options.any():
        parser.print_usage()
        sys.exit(0)

    # Convert the arguments we defined in the argument parser to the actual subcommand that we want
    # delegated.
    cmd: str | None = args.cmd[0] if args.cmd else None
    argv: list[str] = args.cmd[1:] + args.args

    if cmd in ("a", "auth"):
        # The `auth` comand does not require any current project information, it can be used globally.
        auth(f"{parser.prog} auth", argv)

    # The project details and build environment manager are relevant for any command that we are delegating.
    # This includes the built-in `lock` command.
    config = TomlConfigFile(DEFAULT_CONFIG_PATH)
    project = load_project(Path.cwd(), outdated_check=not env_options.upgrade)
    manager = BuildEnvManager(project.directory / BUILDENV_PATH, AuthModel(config, DEFAULT_CONFIG_PATH))

    # Execute environment operations before delegating the command.

    is_lock_command = cmd in ("lock", "l")

    if env_options.status:
        if cmd or argv:
            eprint("error: --status option must be used alone")
            sys.exit(1)
        _print_env_status(manager, project)
        sys.exit(0)

    if env_options.uninstall:
        if cmd or argv:
            eprint("error: --uninstall option must be used alone")
            sys.exit(1)
        manager.remove()
        sys.exit(0)
    if env_options.any() or not is_lock_command:
        _ensure_installed(
            manager,
            project,
            env_options.reinstall or (os.getenv("KRAKENW_REINSTALL") == "1"),
            env_options.upgrade,
            env_options.use,
        )

    if cmd is None:
        assert not argv
        sys.exit(0)

    elif cmd in ("l", "lock"):
        lock(f"{parser.prog} lock", argv, manager, project)

    else:
        if project.directory.absolute() != Path.cwd():
            argv = ["-p", str(project.directory)] + argv
        command = [cmd, *argv]
        eprint("$", " ".join(map(shlex.quote, ["kraken"] + command)))
        environment = manager.get_environment()
        environment.dispatch_to_kraken_cli(command)


if __name__ == "__main__":
    main()
