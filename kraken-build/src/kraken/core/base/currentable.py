"""
Provides the :class:`Currentable` base class which outfits subclasses with an :meth:`~Currentable.as_current` method
that makes a single instance of a class available globally (across threads, but not thread-safe).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, ClassVar, Generic, TypeVar, cast, overload

from kraken.common import NotSet

T = TypeVar("T")
U = TypeVar("U")


class CurrentProvider(ABC, Generic[T]):
    """
    Protocol for classes that provide a :meth:`current` classmethod.
    """

    @overload
    @classmethod
    def current(cls) -> T:
        """Returns the current context or raises a :class:`RuntimeError`."""

    @overload
    @classmethod
    def current(cls, fallback: U) -> T | U:
        """Returns the current context or *fallback*."""

    @classmethod
    def current(cls, fallback: U | NotSet = NotSet.Value) -> T | U:
        try:
            return cls._get_current_object()
        except RuntimeError:
            if fallback is NotSet.Value:
                raise
            return fallback

    @classmethod
    @abstractmethod
    def _get_current_object(cls) -> T:
        raise NotImplementedError


class Currentable(CurrentProvider[T]):
    """
    Base class for classes that should have a :meth:`as_current` method.
    """

    __current: ClassVar[Any | None] = None  # note: ClassVar cannot contain type variables

    @contextmanager
    def as_current(self) -> Iterator[T]:
        """
        A context manager that makes the instance *self* available globally to be retrieved with :meth:`current`.

        This method is not thread-safe, and the object will be available for all threads.
        """

        prev = type(self).__current
        try:
            type(self).__current = self
            yield cast(T, self)
        finally:
            type(self).__current = prev

    # CurrentProvider

    @classmethod
    def _get_current_object(cls) -> T:
        if cls.__current is None:
            raise RuntimeError(f"No current object for type `{cls.__name__}`")
        return cast(T, cls.__current)
