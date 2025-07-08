import argparse
import inspect
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
        if verbosity >= 2:
            level = "DEBUG"
        elif verbosity >= 1:
            level = "INFO"
        elif verbosity == 0:
            level = "WARNING"
        elif verbosity < 0:
            level = "ERROR"
        else:
            assert False, verbosity

        # Intercept standard logs and send them to Loguru.
        class InterceptHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                # Get corresponding Loguru level if it exists.
                level: str | int
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno

                # Find caller from where originated the logged message.
                frame, depth = inspect.currentframe(), 0
                while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
                    frame = frame.f_back
                    depth += 1

                logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

        if verbosity >= 3:
            log_format = "<dim>[{time:HH:mm:ss} <lvl>{level:>8}</lvl> <cyan>{name}</cyan>:<cyan>{line}</cyan>]</dim> <lvl>{message}</lvl>"
        else:
            log_format = "<dim>[{time:HH:mm:ss} <lvl>{level:>8}</lvl>]</dim> <lvl>{message}</lvl>"

            # Disable some noisy loggers by default.
            logging.getLogger("keyring").setLevel(logging.WARNING)

        logger.remove()
        logger.add(sys.stderr, level=level, format=log_format)


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
