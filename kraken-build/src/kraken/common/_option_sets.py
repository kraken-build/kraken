import argparse
import logging
import sys
from dataclasses import dataclass
from typing import ClassVar

from loguru import logger


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
        verbosity = self.verbosity - self.quietness
        if verbosity > 1:
            level = "DEBUG"
        elif verbosity > 0:
            level = "INFO"
        elif verbosity == 0:
            level = "WARNING"
        elif verbosity < 0:
            level = "ERROR"
        else:
            assert False, verbosity

        # note: this is for components that don't use the `loguru.logger`.
        logging.basicConfig(level=getattr(logging, level), format="%(asctime)s | %(levelname)s | %(message)s")

        logger.remove()
        logger.add(sys.stderr, level=level)


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
