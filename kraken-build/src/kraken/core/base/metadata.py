from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, overload

T = TypeVar("T")


class MetadataContainer:
    """
    A base class for classes that shall have a :attr:`metadata` attribute that is intended to contain arbitrary
    objects to store metadata on the object. The metadata can be retrieved later using the :meth:`find_metadata`
    method.
    """

    metadata: list[Any]

    def __init__(self) -> None:
        self.metadata = []

    @overload
    def find_metadata(self, of_type: type[T]) -> T | None:
        """Returns the first entry in the :attr:`metadata` that is of the specified type."""

    @overload
    def find_metadata(self, of_type: type[T], create: Callable[[], T]) -> T:
        """Returns the first entry in :attr:`metadata`, or creates one."""

    def find_metadata(self, of_type: type[T], create: Callable[[], T] | None = None) -> T | None:
        obj = next((x for x in self.metadata if isinstance(x, of_type)), None)
        if obj is None and create is not None:
            obj = create()
            self.metadata.append(obj)
        return obj
