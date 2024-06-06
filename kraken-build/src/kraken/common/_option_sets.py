import argparse
from dataclasses import dataclass
from functools import wraps
from typing import Any


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

    def init_logging(self) -> None:
        import logging

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

        logging.basicConfig(level=level, format="%(message)s", handlers=[RichHandler()])


class ColorOptions:
    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--no-color",
            dest="no_color",
            action="store_true",
            help="disable colored output",
        )

    @staticmethod
    def init_color(args: argparse.Namespace) -> None:
        no_color: bool = getattr(args, "no_color", False)

        raise Exception("FOOBAR")

        import termcolor
        from termcolor import colored

        @wraps(colored)
        def _colored(text: str, *args: Any, **kwargs: Any) -> str:
            if no_color:
                return text
            kwargs.setdefault("force_color", True)
            return colored(text, *args, **kwargs)

        termcolor.colored = _colored
