import argparse


def propagate_argparse_formatter_to_subparser(parser: argparse.ArgumentParser) -> None:
    """Propagates the formatter on *parser* to all subparsers."""

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for subparser in set(action._name_parser_map.values()):
                subparser.formatter_class = parser.formatter_class
                propagate_argparse_formatter_to_subparser(subparser)
