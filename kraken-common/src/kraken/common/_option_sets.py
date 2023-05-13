import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class LoggingOptions:
    verbosity: int
    quietness: int

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("logging options")
        group.add_argument(
            "-v",
            dest="verbosity",
            action="count",
            default=0,
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

    def init_logging(self, format: "str | None" = None) -> None:
        import logging

        from termcolor import colored

        verbosity = self.verbosity - self.quietness

        if format is None:
            format = " | ".join(
                (
                    colored("%(levelname)-7s", "magenta"),
                    colored("%(name)-24s", "blue"),
                    colored("%(message)s", "cyan"),
                )
            )

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

        logging.basicConfig(level=level, format=format)
