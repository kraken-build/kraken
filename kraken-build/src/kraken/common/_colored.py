from collections.abc import Iterable

from termcolor import colored as _colored

__all__ = ["colored", "Attribute", "Color", "Highlight"]

COLORS_ENABLED = True

# For backwards compatibility < v0.45.0, which is before the termcolor v3 upgrade.
Attribute = str
Color = str
Highlight = str


def colored(
    text: object,
    color: str | tuple[int, int, int] | None = None,
    on_color: str | tuple[int, int, int] | None = None,
    attrs: Iterable[str] | None = None,
    *,
    no_color: bool | None = None,
    force_color: bool | None = True,
) -> str:
    if not COLORS_ENABLED:
        return str(text)
    return _colored(text, color, on_color, attrs=attrs, force_color=force_color, no_color=no_color)
