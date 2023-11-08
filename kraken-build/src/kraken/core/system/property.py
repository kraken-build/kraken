"""
This module provides the property API which is used to describe properties on Kraken objects.

Properties are used to represent data on an object that is evaluated lazily. A property value can be filled
with static data or derived from other properties. When a property has no value set, it raises a
:class:`Supplier.Empty` exception (also accessible as :attr:`Property.Empty`).

A property may be marked as an "output" property, which means that its value is only known at a later stage
when some work has been performed (e.g. the owning Kraken task was executed). If such a property is evaluated
before the value is available, a :class:`Property.Deferred` exception is raised instead.
"""

from __future__ import annotations

import copy
import dataclasses
import sys
import weakref
from collections.abc import Callable, Iterable, Mapping, Sequence
from operator import concat
from pathlib import Path
from typing import Any, ClassVar, TypeVar, cast

import deprecated
from typeapi import (
    AnnotatedTypeHint,
    ClassTypeHint,
    LiteralTypeHint,
    TupleTypeHint,
    TypeHint,
    UnionTypeHint,
    get_annotations,
)

from kraken.common import NotSet, Supplier, not_none

T = TypeVar("T")
U = TypeVar("U")


@dataclasses.dataclass
class PropertyConfig:
    """Used to annotate properties, to configure the property.

    .. code:: Example

        from kraken.core.system.property import Object, Property, output
        from typing_extensions import Annotated

        class MyObj(Object):
            a: Annotated[Property[int], PropertyConfig(output=True)]
    """

    output: bool = False
    default: Any | NotSet = NotSet.Value
    default_factory: Callable[[], Any] | NotSet = NotSet.Value
    help: str | None = None


@dataclasses.dataclass
class PropertyDescriptor:
    name: str
    is_output: bool
    default: Any | NotSet
    default_factory: Callable[[], Any] | NotSet
    item_type: TypeHint
    help: str | None = None

    def has_default(self) -> bool:
        return not (self.default is NotSet.Value and self.default_factory is NotSet.Value)

    def get_default(self) -> Any:
        if self.default is not NotSet.Value:
            return copy.deepcopy(self.default)
        elif self.default_factory is not NotSet.Value:
            return self.default_factory()
        else:
            raise RuntimeError(f"property {self.name!r} has no default value")


class Property(Supplier[T]):
    """A property represents an input or output parameter of an :class:`Object`."""

    class Deferred(Exception):
        """
        This exception is raised when an output property has no value set. It is distinct from the
        :class:`Supplier.Empty` exception in that it will propagate to the caller in any case.
        """

        def __init__(self, property: Property[Any], message: str | None = None) -> None:
            self.property = property
            self.message = message

        def __str__(self) -> str:
            if self.message:
                return f"{self.message} ({self.property})"
            else:
                return f"the value of {self.property} will be known at a later time"

    ValueAdapter = Callable[[Any], Any]

    # This dictionary is a registry for type adapters that are used to ensure that values passed
    # into a property with :meth:`set()` are of the appropriate type. If a type adapter for a
    # particular type does not exist, a basic type check is performed. Note that the type adaptation
    # is not particularly sophisticated at this point and will not apply on items in nested structures.
    VALUE_ADAPTERS: ClassVar[dict[type, ValueAdapter]] = {}

    @staticmethod
    def output(*, help: str | None = None) -> Any:
        """Assign the result of this function as a default value to a property on the class level of an :class:`Object`
        subclass to mark it as an output property. This is an alternative to using the :class:`typing.Annotated` type
        hint.

        .. code:: Example

            from kraken.core.system.property import Object, Property, output

            class MyObj(Object):
                a: Property[int] = output()
        """

        return PropertyConfig(output=True, help=help)

    @staticmethod
    def required(*, help: str | None = None) -> Any:
        """
        Assign the result of this function as a default value to a property class to declare that it is required. This
        is the default behaviour of the a property, so this function is only useful to specify a help text or to make
        it more explicit in the code.
        """

        return PropertyConfig(help=help)

    @staticmethod
    def default(value: Any, *, help: str | None = None) -> Any:
        """Assign the result of this function as a default value to a property to declare it's default value."""

        return PropertyConfig(default=value, help=help)

    @staticmethod
    def default_factory(func: Callable[[], Any], help: str | None = None) -> Any:
        """Assign the result of this function as a default value to a property to declare it's default factory."""

        return PropertyConfig(default_factory=func, help=help)

    @staticmethod
    @deprecated.deprecated(reason="use Property.required(), .default() or .default_factory() instead")
    def config(
        output: bool = False,
        default: Any | NotSet = NotSet.Value,
        default_factory: Callable[[], Any] | NotSet = NotSet.Value,
    ) -> Any:
        """Assign the result of this function as a default value to a property on the class level of an :class:`Object`
        subclass to configure it's default value or whether it is an output property. This is an alternative to using
        a :class:`typing.Annotated` type hint.

        .. code:: Example

            from kraken.core.system.property import Object, Property, config

            class MyObj(Object):
                a: Property[int] = config(default=42)
        """

        return PropertyConfig(output, default, default_factory)

    def __init__(
        self,
        owner: PropertyContainer | type[PropertyContainer],
        name: str,
        item_type: TypeHint | Any,
        deferred: bool = False,
        help: str | None = None,
    ) -> None:
        """
        :param owner: The object that owns the property instance.
        :param name: The name of the property.
        :param item_type: The original inner type hint of the property (excluding the Property type itself).
        :param deferred: Whether the property should be initialized with a :class:`DeferredSupplier`.
        :param help: A help text for the property.
        """

        # NOTE(@NiklasRosenstein): We expect that any union member be a ClassTypeHint or TupleTypeHint.
        def _get_types(hint: TypeHint) -> tuple[type, ...]:
            if isinstance(hint, (ClassTypeHint, TupleTypeHint)):
                return (hint.type,)
            elif isinstance(hint, LiteralTypeHint):
                # TODO(@NiklasRosenstein): Add validation to the property to error if a bad value is set.
                return tuple({type(x) for x in hint.values})
            else:
                raise RuntimeError(f"unexpected Property type hint {hint!r}")

        # Determine the accepted types of the property.
        item_type = item_type if isinstance(item_type, TypeHint) else TypeHint(item_type)
        if isinstance(item_type, UnionTypeHint):
            accepted_types = tuple(concat(*map(_get_types, item_type)))
        else:
            accepted_types = _get_types(item_type)

        # Ensure that we have value adapters for every accepted type.
        for accepted_type in accepted_types:
            if accepted_type not in self.VALUE_ADAPTERS:
                if not isinstance(accepted_type, type):
                    raise ValueError(f"missing value adapter for type {accepted_type!r}")
        assert len(accepted_types) > 0

        self.owner = owner
        self.name = name
        self.help = help
        self.accepted_types = accepted_types
        self.item_type = item_type
        self._value: Supplier[T] = DeferredSupplier(self) if deferred else Supplier.void()
        self._derived_from: Sequence[Supplier[Any]] = ()
        self._finalized = False
        self._error_message: str | None = None

    def __repr__(self) -> str:
        try:
            owner_fmt = str(self.owner)
        except Exception:
            owner_fmt = type(self.owner).__name__ + "(<exception during fmt>)"
        return f"Property({owner_fmt}.{self.name})"

    def _adapt_value(self, value: Any) -> Any:
        errors = []
        for accepted_type in self.accepted_types:
            try:
                adapter = self.VALUE_ADAPTERS[accepted_type]
            except KeyError:
                if isinstance(accepted_type, type):
                    adapter = _type_checking_adapter(accepted_type)
                else:
                    raise
            try:
                return adapter(value)
            except TypeError as exc:
                errors.append(exc)
        raise TypeError(f"{self}: " + "\n".join(map(str, errors))) from (errors[0] if len(errors) == 1 else None)

    @property
    def value(self) -> Supplier[T]:
        return self._value

    def derived_from(self) -> Iterable[Supplier[Any]]:
        yield self._value
        yield from self._value.derived_from()
        yield from self._derived_from

    def get(self) -> T:
        try:
            return self._value.get()
        except Supplier.Empty:
            raise Supplier.Empty(self, self._error_message)

    def set(self, value: T | Supplier[T], derived_from: Iterable[Supplier[Any]] = ()) -> None:
        if self._finalized:
            raise RuntimeError(f"{self} is finalized")
        derived_from = list(derived_from)
        if not isinstance(value, Supplier):
            value = Supplier.of(self._adapt_value(value), derived_from)
            derived_from = ()
        self._value = value
        self._derived_from = derived_from

    def setcallable(self, func: Callable[[], T], derived_from: Iterable[Supplier[Any]] = ()) -> None:
        if self._finalized:
            raise RuntimeError(f"{self} is finalized")
        if not callable(func):
            raise TypeError('"func" must be callable')
        self._value = Supplier.of_callable(func, list(derived_from))
        self._derived_from = ()

    def setmap(self, func: Callable[[T], T]) -> None:
        if self._finalized:
            raise RuntimeError(f"{self} is finalized")
        if not callable(func):
            raise TypeError('"func" must be callable')
        self._value = self._value.map(func)

    def setdefault(self, value: T | Supplier[T]) -> None:
        if self._finalized:
            raise RuntimeError(f"{self} is finalized")
        if self._value.is_void():
            self.set(value)

    def setfinal(self, value: T | Supplier[T]) -> None:
        self.set(value)
        self.finalize()

    def seterror(self, message: str) -> None:
        """Set an error message that should be included when the property is read."""

        self._error_message = message

    def clear(self) -> None:
        self.set(Supplier.void())

    def finalize(self) -> None:
        """Prevent further modification of the value in the property."""

        if not self._finalized:
            self._finalized = True

    def provides(self, type_: type) -> bool:
        """Returns `True` if the property may provide an instance or a sequence of the given *type_*."""

        if isinstance(self.item_type, UnionTypeHint):
            types = list(self.item_type)
        elif isinstance(self.item_type, ClassTypeHint):
            types = [self.item_type]
        else:
            assert False, self.item_type

        for provided in types:
            if not isinstance(provided, ClassTypeHint):
                continue
            if issubclass(provided.type, type_):
                return True
            if issubclass(provided.type, Sequence) and provided.args and len(provided.args) == 1:
                inner = provided.args[0]
                if issubclass(inner, type_):
                    return True

        return False

    def get_of_type(self, type_: type[U]) -> list[U]:
        """Return the inner value or values of the property as a flat list of *t*. If the property returns only a
        a single value of the specified type, the returned list will contain only that value. If the property instead
        provides a sequence that contains one or more objects of the provided type, only those objects will be
        returned.

        Note that this does not work with generic parametrized types."""

        value = self.get()
        if type_ != object and isinstance(value, type_):
            return [value]
        if isinstance(value, Sequence):
            return [x for x in value if isinstance(x, type_)]
        if type_ == object:
            return [cast(U, value)]
        return []

    @staticmethod
    def value_adapter(type_: type) -> Callable[[ValueAdapter], ValueAdapter]:
        """Decorator for functions that serve as a value adapter for the given *type_*."""

        def decorator(func: Property.ValueAdapter) -> Property.ValueAdapter:
            Property.VALUE_ADAPTERS[type_] = func
            return func

        return decorator

    def is_set(self) -> bool:
        """
        Returns #True if the property has been set to a value, #False otherwise. This is different from #is_empty(),
        because it does not require evaluation of the property value. This method reflects whether #set() has been
        called with any other value than a #VoidSupplier or a #DeferredSupplier.
        """

        return not self._value.is_void()

    # Supplier

    def is_empty(self) -> bool:
        if isinstance(self._value, DeferredSupplier):
            return True
        return super().is_empty()

    # Python Descriptor

    def __set__(self, instance: PropertyContainer, value: T | Supplier[T] | None) -> None:
        instance_prop = vars(instance)[self.name]
        assert isinstance(instance_prop, Property)
        if value is not None or type(None) in self.accepted_types:
            instance_prop.set(value)
        else:
            instance_prop.clear()

    def __get__(self, instance: PropertyContainer | None, owner: type[Any]) -> Property[T]:
        if instance is None:
            return self
        instance_prop = vars(instance)[self.name]
        assert isinstance(instance_prop, Property)
        return instance_prop


class PropertyContainer:
    """Base class. An object's schema is declared as annotations linking to properties."""

    __schema__: ClassVar[Mapping[str, PropertyDescriptor]] = {}

    def __init_subclass__(cls) -> None:
        """Initializes the :attr:`__schema__` by introspecting the class annotations."""

        schema: dict[str, PropertyDescriptor] = {}
        base: type[PropertyContainer]
        for base in cls.__bases__:
            if issubclass(base, PropertyContainer):
                schema.update(base.__schema__)

        for key, hint in get_annotations(cls).items():
            hint = TypeHint(hint)
            config: PropertyConfig | None = None

            # Unwrap annotatations, looking for a PropertyConfig annotation.
            if isinstance(hint, AnnotatedTypeHint):
                config = next((x for x in hint.metadata if isinstance(x, PropertyConfig)), None)
                hint = TypeHint(hint.type)

            # Check if :func:`output()` or :func:`default()` was used to configure the property.
            if hasattr(cls, key) and isinstance(getattr(cls, key), PropertyConfig):
                assert config is None, "PropertyConfig cannot be on both an attribute and type annotation"
                config = getattr(cls, key)
                delattr(cls, key)

            # Is the hint pointing to a Property type?
            if isinstance(hint, ClassTypeHint) and hint.type == Property:
                assert isinstance(hint, ClassTypeHint) and hint.type == Property, hint
                assert hint.args is not None and len(hint.args) == 1, hint
                config = config or PropertyConfig()
                schema[key] = PropertyDescriptor(
                    name=key,
                    is_output=config.output,
                    default=config.default,
                    default_factory=config.default_factory,
                    item_type=hint[0].evaluate(vars(sys.modules[cls.__module__])),
                    help=config.help,
                )

            # The attribute is annotated as an output but not actually typed as a property?
            elif config:
                raise RuntimeError(
                    f"Type hint for {cls.__name__}.{key} is annotated as a 'PropertyConfig', but not actually "
                    "typed as a 'Property'."
                )

            cls.__schema__ = schema

        # Make sure there's a Property descriptor on the class for every property in the schema.
        for key, value in cls.__schema__.items():
            setattr(cls, key, Property[Any](cls, key, value.item_type, value.is_output, value.help))

    def __init__(self) -> None:
        """Creates :class:`Properties <Property>` for every property defined in the object's schema."""

        for key, desc in self.__schema__.items():
            prop = Property[Any](self, key, desc.item_type, desc.is_output, desc.help)
            vars(self)[key] = prop
            if desc.has_default():
                prop.setdefault(desc.get_default())


class DeferredSupplier(Supplier[Any]):
    def __init__(self, property: Property[Any]) -> None:
        self.property = weakref.ref(property)

    def derived_from(self) -> Iterable[Supplier[Any]]:
        return ()

    def get(self) -> Any:
        raise Property.Deferred(not_none(self.property()))

    def is_void(self) -> bool:
        return True


# Register common value adapters


def _type_checking_adapter(type_: type) -> Property.ValueAdapter:
    def func(value: Any) -> Any:
        if not isinstance(value, type_):
            raise TypeError(f"expected {type_.__name__}, got {type(value).__name__}")
        return value

    func.__name__ = f"check_{type_.__name__}"
    return func


@Property.value_adapter(Path)
def _adapt_path(value: Any) -> Path:
    if isinstance(value, str):
        return Path(value)
    if not isinstance(value, Path):
        raise TypeError(f"expected Path, got {type(value).__name__}")
    return value
