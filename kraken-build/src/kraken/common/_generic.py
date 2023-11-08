from __future__ import annotations

import enum
from collections.abc import Callable, Iterable
from typing import TypeVar

__all__ = [
    "flatten",
    "not_none",
]

T = TypeVar("T")


def flatten(it: Iterable[Iterable[T]]) -> Iterable[T]:
    """
    Flatten a nested iterable into a single iterable.
    """

    for item in it:
        yield from item


def not_none(v: T | None, message: str | Callable[[], str] = "expected not-None") -> T:
    """
    Raise a :class:`RuntimeError` if *v* is `None`, otherwise return *v*.
    """

    if v is None:
        if callable(message):
            message = message()
        raise RuntimeError(message)
    return v


class NotSet(enum.Enum):
    Value = 1
