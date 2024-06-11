from collections.abc import Iterable

from termcolor import colored as _colored
from termcolor._types import Attribute, Color, Highlight

__all__ = ["colored", "Attribute", "Color", "Highlight"]

COLORS_ENABLED = True


def colored(
    text: str,
    color: Color | None = None,
    on_color: Highlight | None = None,
    attrs: Iterable[Attribute] | None = None,
) -> str:
    if not COLORS_ENABLED:
        return text
    return _colored(text, color, on_color, attrs=attrs, force_color=True)
