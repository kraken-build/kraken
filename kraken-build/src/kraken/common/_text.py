import re
import textwrap
import uuid
from collections.abc import Callable
from typing import Protocol


class SupportsLen(Protocol):
    def __len__(self) -> int: ...


def pluralize(word: str, count: "int | SupportsLen") -> str:
    """
    Very naive implementation to pluralize english words (simply appends an s).
    """

    if not isinstance(count, int):
        count = len(count)
    return word if count == 1 else f"{word}s"


def inline_text(text: str) -> str:
    """
    A helper that dedents *text* and replaces a single newline with a single whitespace, yet double newlines are
    kept in place. To enforce a normal linebreak, add a backslash before a single newline.
    """

    marker = f"---{uuid.uuid1()}---"

    text = textwrap.dedent(text).strip()
    text = text.replace("\n\n", marker)
    text = re.sub(r"(?<!\\)\n(?!\n)", " ", text)  # Replace single line newlines by whitespace unless escaped
    text = re.sub(r"\\\n", "\n", text)
    text = text.replace(marker, "\n\n")
    return text


class lazy_str:
    """
    Delegates to a function to convert to a string.
    """

    def __init__(self, func: Callable[[], str]) -> None:
        self._func = func

    def __str__(self) -> str:
        return self._func()
