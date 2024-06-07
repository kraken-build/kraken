from collections.abc import Iterable

from termcolor import colored as _colored

COLORS_ENABLED = True


def colored(
    text: str,
    color: str | None = None,
    on_color: str | None = None,
    attrs: Iterable[str] | None = None,
) -> str:
    if not COLORS_ENABLED:
        return text
    return _colored(text, color, on_color, attrs=attrs, force_color=True)
