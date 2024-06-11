import argparse
import logging
from dataclasses import dataclass
from typing import ClassVar

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoggingOptions:
    verbosity: int
    quietness: int

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser, default_verbosity: int = 0) -> None:
        group = parser.add_argument_group("logging options")
        group.add_argument(
            "-v",
            dest="verbosity",
            action="count",
            default=default_verbosity,
            help="increase the log level (can be specified multiple times)",
        )
        group.add_argument(
            "-q",
            dest="quietness",
            action="count",
            default=0,
            help="decrease the log level (can be specified multiple times)",
        )

    @staticmethod
    def available(args: argparse.Namespace) -> bool:
        return hasattr(args, "verbosity")

    @classmethod
    def collect(cls, args: argparse.Namespace) -> "LoggingOptions":
        return cls(
            verbosity=args.verbosity,
            quietness=args.quietness,
        )

    def init_logging(self, force_color: bool = False) -> None:
        import logging

        from rich.console import Console
        from rich.logging import RichHandler

        verbosity = self.verbosity - self.quietness
        if verbosity > 1:
            level = logging.DEBUG
        elif verbosity > 0:
            level = logging.INFO
        elif verbosity == 0:
            level = logging.WARNING
        elif verbosity < 0:
            level = logging.ERROR
        else:
            assert False, verbosity

        console = Console(force_terminal=True if force_color else None)
        logging.basicConfig(level=level, format="%(message)s", handlers=[RichHandler(console=console)])


@dataclass
class ColorOptions:
    """
    Adds a `--no-color` option to the argument parser. Use [init_color] to monkey-patch the [termcolor] module
    to force color output unless the `--no-color` option is set. This ensures we have colored output even in CI
    environments by default.
    """

    no_color: bool

    _termcolor_monkeypatched: ClassVar[bool] = False

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--no-color",
            dest="no_color",
            action="store_true",
            help="disable colored output",
        )

    @staticmethod
    def collect(args: argparse.Namespace) -> "ColorOptions":
        return ColorOptions(
            no_color=args.no_color,
        )

    def init_color(self) -> None:
        from kraken.common import _colored

        if self.no_color:
            _colored.COLORS_ENABLED = False
