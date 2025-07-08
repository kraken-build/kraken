import re
from collections.abc import Iterator, Sequence
from typing import TextIO

from ._colored import colored

REGEX_ANSI_ESCAPE = re.compile(
    r"""
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or [ for CSI, followed by a control sequence
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
""",
    re.VERBOSE,
)


class AsciiTable:
    """
    A very simple ASCII table formatter.

    Supports correctly calculating the width of cells even if they are already ANSI formatted.
    """

    #: A list of the header text cells to display at the top of the table.
    headers: list[str]

    #: A list of rows to display in the table. Note that each row should have at least as many elements as
    #: :attr:`headers`, otherwise you will face an :class:`IndexError` in :meth:`print`.
    rows: list[Sequence[str]]

    def __init__(self) -> None:
        self.headers = []
        self.rows = []

    def __iter__(self) -> Iterator[Sequence[str]]:
        yield self.headers
        yield from self.rows

    def print(self, fp: "TextIO | None" = None) -> None:
        widths = [
            max(len(REGEX_ANSI_ESCAPE.sub("", row[col_idx])) for row in self) for col_idx in range(len(self.headers))
        ]
        for row_idx, row in enumerate(self):
            if row_idx == 0:
                row = [colored(x.ljust(widths[col_idx]), attrs=["bold"]) for col_idx, x in enumerate(row)]
            else:
                row = [x.ljust(widths[col_idx]) for col_idx, x in enumerate(row)]
            if row_idx == 1:
                print("  ".join("-" * widths[idx] for idx in range(len(row))), file=fp)
            print("  ".join(row[idx].ljust(widths[idx]) for idx in range(len(row))), file=fp)
