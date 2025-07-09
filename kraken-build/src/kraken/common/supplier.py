"""This module provides provides the :class:`Supplier` interface which is used to represent values that can be
calculated lazily and track provenance of such computations."""

import abc
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Generic, TypeVar, overload

from ._generic import NotSet

T = TypeVar("T", covariant=True)
U = TypeVar("U")
K = TypeVar("K")
V = TypeVar("V")


class Supplier(Generic[T], abc.ABC):
    """Base class for value suppliers."""

    class Empty(Exception):
        """Raised when a supplier cannot provide a value."""

        def __init__(self, supplier: "Supplier[Any]", message: "str | None" = None) -> None:
            self.supplier = supplier
            self.message = message

        def __str__(self) -> str:
            if self.message:
                return f"{self.message} ({self.supplier})"
            else:
                return str(self.supplier)

    @abc.abstractmethod
    def derived_from(self) -> Iterable["Supplier[Any]"]:
        """Return an iterable that yields all suppliers that this supplier is derived from."""

    @abc.abstractmethod
    def get(self) -> T:
        """Return the value of the supplier. Depending on the implemenmtation, this may defer to other suppliers."""

    @overload
    def get_or(self, fallback: None) -> "T | None": ...

    @overload
    def get_or(self, fallback: U) -> "T | U": ...

    def get_or(self, fallback: U | None) -> "T | U | None":
        """Return the value of the supplier, or the *fallback* value if the supplier is empty."""
        try:
            return self.get()
        except Supplier.Empty:
            return fallback

    def get_or_raise(self, get_exception: Callable[[], Exception]) -> T:
        """Return the value of the supplier, or raise the exception provided by *get_exception* if empty."""
        try:
            return self.get()
        except Supplier.Empty:
            raise get_exception()

    def is_empty(self) -> bool:
        """Returns `True` if the supplier is empty."""
        try:
            self.get()
        except Supplier.Empty:
            return True
        else:
            return False

    def is_filled(self) -> bool:
        """Returns `True` if the supplier is not empty."""
        return not self.is_empty()

    def is_void(self) -> bool:
        return False

    def map(self, func: Callable[[T], U]) -> "Supplier[U]":
        """Maps *func* over the value in the supplier."""

        return MapSupplier(func, self)

    def once(self) -> "Supplier[T]":
        """Cache the value forever once :attr:`get` is called."""

        return OnceSupplier(self)

    def __getitem__(self: "Supplier[Mapping[K, V]]", key: K) -> "GetItemSupplier[V]":
        return GetItemSupplier(key, self)

    def lineage(self) -> Iterable[tuple["Supplier[Any]", list["Supplier[Any]"]]]:
        """Iterates over all suppliers in the lineage.

        Yields:
            A supplier and the suppliers it is derived from.
        """

        stack: list["Supplier[Any]"] = [self]
        while stack:
            current = stack.pop(0)
            derived_from = list(current.derived_from())
            yield current, derived_from
            stack += derived_from

    @staticmethod
    def of(value: "T | Supplier[T]", derived_from: Sequence["Supplier[Any]"] = ()) -> "Supplier[T]":
        """
        Coercion for ``T | Supplier[T] -> Supplier[T]``. This is useful when accepting parameters for task factories
        that could either be a "hard" value or derived from properties of other tasks.

        .. code-block:: python

            def my_task(name: str, files: Sequence[str | Path] | Property[Sequence[Path]]) -> MyTask:
                from kraken.build import project
                task = project.task(name, MyTask)
                task.files = (
                    Supplier[Sequence[str | Path]]
                    .of(files)
                    .map(lambda files: [project.directory / f for f in files])
                )
                return task

        Note that Mypy (state v1.16.1) cannot properly refine types when ``T`` is a union type, meaning you often
        need to explicitly define ``T`` (as also shown in the example above).

        .. code-block:: python

            >>> from typing_extensions import assert_type
            >>> assert_type( Supplier.of("foo"),                            Supplier[str]       )  # OK (simple)
            >>> assert_type( Supplier.of(cast(str | int, "foo"),            Supplier[object]    )  # types unrefined
            >>> assert_type( Supplier[str | int].of(cast(str | int, "foo"), Supplier[int | str] )  # OK
        """

        if isinstance(value, Supplier):
            return value
        return OfSupplier(value, derived_from)

    @staticmethod
    def of_callable(func: Callable[[], T], derived_from: Sequence["Supplier[Any]"] = ()) -> "Supplier[T]":
        return OfCallableSupplier(func, derived_from)

    @staticmethod
    def void(from_exc: "Exception | None" = None, derived_from: Sequence["Supplier[Any]"] = ()) -> "Supplier[T]":
        """Returns a supplier that always raises :class:`Empty`."""

        return VoidSupplier(from_exc, derived_from)

    def __repr__(self) -> str:
        try:
            value = self.get_or(NotSet.Value)
        except Exception as exc:
            inner = f"<exception reading value: {exc}>"
        else:
            if value is NotSet.Value:
                inner = "<empty>"
            else:
                inner = f"value={value!r}"
        return f"{type(self).__name__}({inner})"


class MapSupplier(Supplier[U], Generic[T, U]):
    def __init__(self, func: Callable[[T], U], value: Supplier[T]) -> None:
        self._func = func
        self._value = value

    def derived_from(self) -> Iterable[Supplier[Any]]:
        yield self._value

    def get(self) -> U:
        try:
            return self._func(self._value.get())
        except Supplier.Empty:
            raise Supplier.Empty(self)

    def __repr__(self) -> str:
        return f"{self._value}.map({self._func})"

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        assert isinstance(other, MapSupplier)
        return (self._func, self._value) == (other._func, other._value)


class GetItemSupplier(Supplier[V]):
    def __init__(self, key: K, value: Supplier[Mapping[K, V]]) -> None:
        self._key = key
        self._value = value

    def derived_from(self) -> Iterable[Supplier[Any]]:
        yield self._value

    def get(self) -> V:
        value = self._value.get()
        return value[self._key]

    def __repr__(self) -> str:
        return f"{self._value}[{self._key}]"

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        assert isinstance(other, GetItemSupplier)
        return (self._key, self._value) == (other._key, other._value)


class OnceSupplier(Supplier[T]):
    _value: "T | NotSet" = NotSet.Value
    _empty: "Supplier.Empty | None" = None

    def __init__(self, delegate: Supplier[T]) -> None:
        self._delegate = delegate

    def derived_from(self) -> Iterable[Supplier[Any]]:
        yield self._delegate

    def get(self) -> T:
        if self._empty is not None:
            raise Supplier.Empty(self) from self._empty
        if self._value is NotSet.Value:
            try:
                self._value = self._delegate.get()
            except Supplier.Empty as exc:
                self._empty = exc
                raise Supplier.Empty(self) from exc
        return self._value

    def __repr__(self) -> str:
        return f"{self._delegate}.once()"

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        assert isinstance(other, OnceSupplier)
        return (self._delegate,) == (other._delegate,)


class OfCallableSupplier(Supplier[T]):
    def __init__(self, func: Callable[[], T], derived_from: Sequence[Supplier[Any]]) -> None:
        self._func = func
        self._derived_from = derived_from

    def derived_from(self) -> Iterable[Supplier[Any]]:
        return self._derived_from

    def get(self) -> T:
        return self._func()

    def __repr__(self) -> str:
        return f"Supplier.of_callable({self._func})"

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        assert isinstance(other, OfCallableSupplier)
        return (self._func, self._derived_from) == (other._func, other._derived_from)


class OfSupplier(Supplier[T]):
    def __init__(self, value: T, derived_from: Sequence[Supplier[Any]]) -> None:
        self._value = value
        self._derived_from = tuple(derived_from)

    def derived_from(self) -> Iterable[Supplier[Any]]:
        return self._derived_from

    def get(self) -> T:
        return self._value

    def __repr__(self) -> str:
        return f"Supplier.of({self._value})"

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        assert isinstance(other, OfSupplier)
        return (self._value, self._derived_from) == (other._value, other._derived_from)


class VoidSupplier(Supplier[T]):
    def __init__(self, from_exc: "Exception | None", derived_from: Sequence[Supplier[Any]]) -> None:
        self._from_exc = from_exc
        self._derived_from = tuple(derived_from)

    def derived_from(self) -> Iterable[Supplier[Any]]:
        return self._derived_from

    def get(self) -> T:
        raise Supplier.Empty(self) from self._from_exc

    def is_void(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"Supplier.void(from_exc={self._from_exc})"

    def __hash__(self) -> int:
        return hash((self._from_exc, self._derived_from))

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        assert isinstance(other, VoidSupplier)
        return (self._from_exc, self._derived_from) == (other._from_exc, other._derived_from)
