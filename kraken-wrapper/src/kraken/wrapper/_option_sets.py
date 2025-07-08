from __future__ import annotations

import argparse
import dataclasses
import logging
import os

from kraken.common import EnvironmentType

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class EnvOptions:
    status: bool
    upgrade: bool
    reinstall: bool
    uninstall: bool
    incremental: bool
    no_keyring: bool

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("build environment")
        group.add_argument(
            "--use",
            choices=[v.name for v in EnvironmentType if v.is_wrapped()],
            default=os.getenv("KRAKENW_USE"),
            help="deprecated since v0.45.0.",
        )
        group.add_argument(
            "--status",
            action="store_true",
            help="print the status of the build environment and exit",
        )
        group.add_argument(
            "--upgrade",
            action="store_true",
            help="reinstall the build environment from the original requirements",
        )
        group.add_argument(
            "--reinstall",
            action="store_true",
            default=os.getenv("KRAKENW_REINSTALL") == "1",
            help="reinstall the build environment from the lock file [env: KRAKENW_REINSTALL=1]",
        )
        group.add_argument(
            "--uninstall",
            action="store_true",
            help="uninstall the build environment",
        )
        group.add_argument(
            "--incremental",
            action="store_true",
            default=os.getenv("KRAKENW_INCREMENTAL") == "1",
            help="re-use an existing build environment. Improves installation time after an update to the buildscript\n"
            "dependencies, but does not upgrade all packages to latest. [env: KRAKENW_INCREMENTAL=1]",
        )
        group.add_argument(
            "--show-install-logs",
            action="store_true",
            default=os.getenv("KRAKENW_SHOW_INSTALL_LOGS") == "1",
            help="deprecated since v0.45.0. has no effect [env: KRAKENW_SHOW_INSTALL_LOGS=1]",
        )

        group = parser.add_argument_group("authentication")
        group.add_argument(
            "--no-keyring",
            action="store_true",
            default=os.getenv("KRAKENW_NO_KEYRING") == "1",
            help="disable the use of the keyring package for loading and storing credentials. "
            "[env: KRAKENW_NO_KEYRING=1]",
        )

    @classmethod
    def collect(cls, args: argparse.Namespace) -> EnvOptions:
        if args.use:
            logger.warning(
                "deprecated option KRAKENW_USE/--use was specified. the option is deprecated since krakenw v0.45.0"
            )

        if args.show_install_logs:
            logger.warning(
                "deprecated option KRAKENW_SHOW_INSTALL_LOGS/--show-install-logs was specified. the option is "
                "deprecated since krakenw v0.45.0"
            )

        return cls(
            status=args.status,
            upgrade=args.upgrade,
            reinstall=args.reinstall,
            uninstall=args.uninstall,
            incremental=args.incremental,
            no_keyring=args.no_keyring,
        )

    def any(self) -> bool:
        return bool(self.status or self.upgrade or self.reinstall or self.uninstall)


@dataclasses.dataclass(frozen=True)
class AuthOptions:
    host: str
    username: str | None
    password: str | None
    password_stdin: bool
    remove: bool
    list: bool
    no_check: bool
    no_mask: bool
    verbose: bool

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("host", nargs="?", help="the host to add the credentials for")
        parser.add_argument(
            "-u",
            "--username",
            help="the username to use when accessing resources on the given host",
        )
        parser.add_argument(
            "-p",
            "--password",
            help="the password to use when accessing resources on the given host (use --password-stdin when possible)",
        )
        parser.add_argument("--password-stdin", action="store_true", help="read the password from stdin")
        parser.add_argument(
            "-r",
            "--remove",
            action="store_true",
            help="remove credentials for the given host",
        )
        parser.add_argument(
            "-l",
            "--list",
            action="store_true",
            help="list configured credentials for the given host",
        )
        parser.add_argument(
            "-s",
            "--no-check",
            action="store_true",
            help="skip checking of auth credentials",
        )
        parser.add_argument(
            "--no-mask",
            action="store_true",
            help="do not mask credentials",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            default=False,
            help="show curl queries to use when authenticating hosts",
        )

    @classmethod
    def collect(cls, args: argparse.Namespace) -> AuthOptions:
        return cls(
            host=args.host,
            username=args.username,
            password=args.password,
            password_stdin=args.password_stdin,
            remove=args.remove,
            list=args.list,
            no_check=args.no_check,
            no_mask=args.no_mask,
            verbose=args.verbose,
        )
