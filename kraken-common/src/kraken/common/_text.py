import re
import textwrap
import uuid
from typing import Callable

from typing_extensions import Protocol


class SupportsLen(Protocol):
    def __len__(self) -> int:
        ...


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


def mask_string(text: str, start_end_char_count: int = 2) -> str:
    """Function to mask a string. Smallest string before a single start/end is not masked is 10

    Args:
        text (str): input string
        start_end_char_count (int, optional): Number of start/end characters to leave unmasked. Defaults to 2.

    Returns:
        str: Masked string
    """

    # If the proportion of unmasked text is more than 22% (4 / 19) of
    # text to mask, mask the entire string. Also applied for non-sensible start_end_char_count values
    if start_end_char_count <= 0 or len(text) == 0 or 2 * start_end_char_count / len(text) > 0.22:
        return "[MASKED]"

    return text[0:start_end_char_count] + "[MASKED]" + text[-start_end_char_count:]


class lazy_str:
    """
    Delegates to a function to convert to a string.
    """

    def __init__(self, func: Callable[[], str]) -> None:
        self._func = func

    def __str__(self) -> str:
        return self._func()
