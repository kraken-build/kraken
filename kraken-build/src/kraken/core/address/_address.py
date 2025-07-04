from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, TypeAlias


class AddressMeta(type):
    """
    Meta class for #Address. Ensures that the copy-constructor returns the original address object.
    """

    def __call__(self, value: Any) -> Address:
        if isinstance(value, Address):
            return value
        obj = object.__new__(Address)
        obj.__init__(value)  # type: ignore[misc]
        return obj


@dataclass(frozen=True)
class Element:
    """Represents an element in the address, which is the text between colon separators (`:`)."""

    VALID_CHARACTERS: ClassVar[str] = r"a-zA-Z0-9/_\-\.\*"
    VALIDATION_REGEX: ClassVar[str] = rf"^[{VALID_CHARACTERS}]+$"
    CURRENT: ClassVar[str] = "."
    PARENT: ClassVar[str] = ".."
    RECURSIVE_WILDCARD: ClassVar[str] = "**"

    # The value of the element. This may contain asterisks for globbing.
    value: str

    #: Whether the element is followed by a question mark to permit resolution failure.
    fallible: bool = False

    __qualname__ = "Address.Element"

    def __post_init__(self) -> None:
        if not re.match(self.VALIDATION_REGEX, self.value):
            raise ValueError(f"invalid address element: {str(self)!r}")

    def __str__(self) -> str:
        if self.fallible:
            return f"{self.value}?"
        return self.value

    def is_current(self) -> bool:
        """
        Returns `True` if the element represents the current project (`.`).

            >>> Address.Element('.').is_current()
            True
        """

        return self.value == self.CURRENT

    def is_parent(self) -> bool:
        """
        Returns `True` if the element represents the parent project (`..`).

            >>> Address.Element('..').is_parent()
            True
        """

        return self.value == self.PARENT

    def is_concrete(self) -> bool:
        """
        Returns `True` if the element is a concrete element that can only have exactly one match. Elements that
        are not concrete have zero or more matches by asterisk (wildcards) in the #value or if #fallible is
        enabled.

            >>> Address.Element("test").is_concrete()
            True
            >>> Address.Element("test*").is_concrete()
            False
            >>> Address.Element("test", fallible=True).is_concrete()
            False
        """

        return not (self.fallible or "*" in self.value)

    def is_recursive_wildcard(self) -> bool:
        return self.value == self.RECURSIVE_WILDCARD

    @classmethod
    def of(cls, value: str) -> Address.Element:
        """
        Creates an element from a string. #fallible is set depending on whether *value* is trailed by a
        question mark.

            >>> Address.Element.of("test")
            Address.Element(value='test', fallible=False)
            >>> Address.Element.of("test?")
            Address.Element(value='test', fallible=True)
            >>> Address.Element.of("test??")
            Traceback (most recent call last):
            ValueError: invalid address element: 'test??'
        """

        fallible = False
        if value.endswith("?"):
            fallible = True
            value = value[:-1]
        return cls(value, fallible)


class Address(metaclass=AddressMeta):
    """
    An address is an immutable parsed representation of a task or project reference, comparable to a filesystem path.
    The separator between elements in the address path is a colon (`:`). Similarly, a dot (`.`) refers to the current
    project, and a double dot (`..`) refers to the parent project.

    The elements of an address can only contain characters matching the :data:`Address.Element.VALIDATION_REGEX`.

    Asterisks are accepted to permit glob pattern matching on the addressable space, where one asterisk (`*`) is
    intended to match only within the same hierarchical level (aka. wildcard), whereas a double asterisk (`**`) is
    used to match any number of levels (aka. recursive wildcard). A trailing question mark on each element is allowed
    to permit that address resolution fails at that element.

        >>> Address(":a?:b").elements
        [Address.Element(value='a', fallible=True), Address.Element(value='b', fallible=False)]
        >>> Address("a:..:b").normalize()
        Address('b')
    """

    SEPARATOR: ClassVar[str] = ":"
    ROOT: ClassVar[Address]
    CURRENT: ClassVar[Address]
    PARENT: ClassVar[Address]
    EMPTY: ClassVar[Address]
    WILDCARD: ClassVar[Address]
    RECURSIVE_WILDCARD: ClassVar[Address]

    _is_absolute: bool
    _is_container: bool
    _elements: list[Element]

    @staticmethod
    def _parse(value: str | Sequence[str]) -> tuple[bool, bool, list[Element]]:
        """Parses a list or strings or lists into (is_absolute, is_container, elements)."""

        # Convert the accepted types of value to a list of strings representing the elements of the address.
        is_absolute = False
        element_strings: list[str]
        if isinstance(value, str):
            if not value:
                element_strings = []
            elif value == Address.SEPARATOR:
                element_strings = [""]
            else:
                element_strings = value.split(Address.SEPARATOR)
        elif isinstance(value, Sequence):
            element_strings = list(value)
        else:
            assert False, type(value)

        # The first element may be an empty string to denote a "root" address.
        is_absolute = False
        if element_strings and not element_strings[0]:
            is_absolute = True
            element_strings.pop(0)

        # The last element may be an empty string to denote a "folder" address.
        is_container = False
        if element_strings and not element_strings[-1]:
            is_container = True
            element_strings.pop(-1)

        # Also, `:` is both absolute and a container
        if is_absolute and len(element_strings) == 0:
            is_container = True

        try:
            elements = [Address.Element.of(x) for x in element_strings]
        except ValueError as exc:
            raise ValueError(f"invalid Address: {Address.SEPARATOR.join(element_strings)!r} (reason: {exc})")

        if len(elements) == 0:
            # For some pathological addresses that are semantically equivalent to `:` (e.g. `:a:..`),
            # it is hard for the caller to easily detect this is a container.
            # Thus, we'll ensure it ourselves here.

            # The root object (":") is both absolute and a container
            # The empty address ("") is neither absolute nor a container
            if is_container or is_absolute:
                is_container = True
                is_absolute = True

        return is_absolute, is_container, elements

    @classmethod
    def create(cls, is_absolute: bool, is_container: bool, elements: list[Element]) -> Address:
        """
        Create a new address object.

        :param is_absolute: Whether the address is absolute (starts with `:`)
        :param elements: The address elements.

            >>> Address.create(True, False, [Address.Element("a", fallible=True), Address.Element("b")])
            Address(':a?:b')
        """

        obj = object.__new__(cls)
        obj._is_absolute = is_absolute
        obj._is_container = is_container
        obj._elements = elements
        obj._hash_key = None

        if len(elements) == 0:
            # For some pathological addresses that are semantically equivalent to `:` (e.g. `:a:..`),
            # it is hard for the caller to easily detect this is a container.
            # Thus, we'll ensure it ourselves here.

            # The root object (":") is both absolute and a container
            # The empty address ("") is neither absolute nor a container
            if obj._is_container or obj._is_absolute:
                obj._is_container = True
                obj._is_absolute = True

        return obj

    def __init__(self, value: str | Sequence[str] | Address) -> None:
        """Create a new Address from a string, sequence of strings or Address.

            >>> Address(":a:b")
            Address(':a:b')
            >>> Address(":a:b".split(":"))
            Address(':a:b')
            >>> Address(["", "a", "b"])
            Address(':a:b')

        Address objects are immutable and are not copied by the constructor (this is implemented via the
        meta class).

            >>> a = Address(':a')
            >>> a is Address(a)
            True

        Use `Address.create()` to construct a new address object from a list of `Address.Element`.
        """

        assert not isinstance(value, Address)
        self._is_absolute, self._is_container, self._elements = self._parse(value)
        self._hash_key: int | None = None

    def __getstate__(self) -> tuple[str]:
        return (str(self),)

    def __setstate__(self, state: tuple[str]) -> None:
        Address.__init__(self, state[0])

    def __str__(self) -> str:
        """
        Returns the string format of the address. Use the `Address` constructor to parse it back into an address.

            >>> str(Address(":a:b"))
            ':a:b'
        """

        value = Address.SEPARATOR.join(str(x) for x in self._elements)
        if self._is_absolute:
            value = f"{Address.SEPARATOR}{value}"
        if self._is_container and not self.is_root():
            # The address must end with a separator...unless it is the root address `:`.
            value = f"{value}{Address.SEPARATOR}"
        return value

    def __repr__(self) -> str:
        """
        Example:

            >>> repr(Address(":a?:b*"))
            "Address(':a?:b*')"
        """

        return f"Address({str(self)!r})"

    def __hash__(self) -> int:
        """
        Returns a stable hash key of the address.
        """

        if self._hash_key is None:
            self._hash_key = hash((Address, self._is_absolute, tuple(self._elements)))
        return self._hash_key

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Address):
            return (self._is_absolute, self._is_container, self._elements) == (
                other._is_absolute,
                other._is_container,
                other._elements,
            )
        return False

    def __len__(self) -> int:
        """
        Returns the number of elements in the address.

        >>> len(Address(":a:b:c"))
        3
        >>> len(Address("a:b:c"))
        3
        """

        return len(self._elements)

    def __getitem__(self, element_index: int) -> Address.Element:
        """
        Returns the _nth_ element in the address.

            >>> Address(":a:b")[1]
            Address.Element(value='b', fallible=False)
        """

        return self._elements[element_index]

    def is_empty(self) -> bool:
        """
        Returns `True` if the address is empty. The empty state is the only invalid state of an address.

            >>> Address("").is_empty()
            True
            >>> Address("a").is_empty()
            False
            >>> bool(Address(""))
            False
            >>> bool(Address("a"))
            True
            >>> Address.EMPTY == Address("")
            True
        """

        return not self._is_absolute and not self._elements

    def __bool__(self) -> bool:
        """
        Returns False if the address is empty, otherwise True.

            >>> bool(Address(":a:b"))
            True
            >>> bool(Address(""))
            False
        """

        return not self.is_empty()

    def is_absolute(self) -> bool:
        """
        Returns `True` if the address is absolute.

            >>> Address(":a").is_absolute()
            True
            >>> Address("a").is_absolute()
            False
            >>> Address("").is_absolute()
            False
        """

        return self._is_absolute

    def is_root(self) -> bool:
        """
        Returns `True` if the address is the root address (`:`).

            >>> Address(":").is_root()
            True
            >>> Address(":a").is_root()
            False
            >>> Address("a").is_root()
            False
            >>> Address("").is_root()
            False
        """
        return self._is_absolute and not self._elements

    def is_concrete(self) -> bool:
        """
        Returns `True` if this is a concrete address. A concrete address is one that is absolute and
        has no globbing elements (see #Address.Element.is_globbing()).

            >>> Address(":a:b").is_concrete()
            True
            >>> Address("a:b").is_concrete()
            False
            >>> Address(":*:b").is_concrete()
            False
            >>> Address(":a:b?").is_concrete()
            False
        """

        return self._is_absolute and all(x.is_concrete() for x in self._elements)

    def is_container(self) -> bool:
        """
        Returns `True` if this is a container address, that is, if it ends with a separator.

            >>> Address(":a:b").is_container()
            False
            >>> Address(":a:b:").is_container()
            True
        """

        return self._is_container

    def normalize(self, *, keep_container: bool = False) -> Address:
        """
        Normalize the address, removing any superfluous elements (`.` for current, `..` for parent). A normalized
        is not a container address. Use #set_container() after #normalize() to make it a container address, or pass
        `True` to the *keep_container* argument to keep the container state.

            >>> Address("").normalize()
            Address('.')
            >>> Address("").normalize(keep_container=True)
            Address('.')
            >>> Address(".").normalize()
            Address('.')
            >>> Address(".").normalize(keep_container=True)
            Address('.')
            >>> Address(".:").normalize()
            Address('.')
            >>> Address(".:").normalize(keep_container=True)
            Address('.:')
            >>> Address(":a:.:b").normalize()
            Address(':a:b')
            >>> Address(":a:.:b").normalize(keep_container=True)
            Address(':a:b')
            >>> Address(":a:..:b").normalize()
            Address(':b')
            >>> Address("..:.:b").normalize()
            Address('..:b')
            >>> Address("..:.:b").normalize(keep_container=True)
            Address('..:b')
            >>> Address("a:b:").normalize()
            Address('a:b')
            >>> Address("a:b:").normalize(keep_container=True)
            Address('a:b:')
            >>> Address("a:b:.").normalize(keep_container=True)
            Address('a:b')
        """

        elements: list[Address.Element] = []
        stack = list(reversed(self._elements))
        while stack:
            current = stack.pop()
            if current.is_parent() and elements:
                elements.pop()
            elif current.is_current():
                pass
            else:
                elements.append(current)
        if not self._is_absolute and not elements:
            elements = [Address.Element(Address.Element.CURRENT, False)]
        return Address.create(self._is_absolute, self.is_container() and keep_container, elements)

    def concat(self, address: str | Address) -> Address:
        """
        Concatenate two addresses. If *address* is absolute, return *address*.

            >>> Address(":a").concat("b:c")
            Address(':a:b:c')
            >>> Address(":a").concat(Address(":b"))
            Address(':b')
            >>> Address(":a").concat(Address("."))
            Address(':a:.')
        """

        if isinstance(address, str):
            address = Address(address)
        if address._is_absolute:
            return address
        return Address.create(self._is_absolute, address._is_container, self._elements + address._elements)

    def append(self, element: str | Element) -> Address:
        """
        Return a new address with one element appended.

            >>> Address(":").append("a")
            Address(':a')
            >>> Address(":a:.").append(".")
            Address(':a:.:.')
        """

        if isinstance(element, str):
            element = Address.Element.of(element)
        assert isinstance(element, Address.Element), type(element)
        return Address.create(self._is_absolute, False, self._elements + [element])

    def set_container(self, is_container: bool) -> Address:
        """
        Return a copy of this address with the container flag set to the given value. The container flag indicates
        whether the string representation of the address is followed by a colon (`:`). This status is irrelevant
        for the root address, as it is always a container.

            >>> Address(":a").set_container(True)
            Address(':a:')
            >>> Address(":a:").set_container(False)
            Address(':a')

        Attempting to set the container status to `False` for the root address will raise a #ValueError. Attempting
        to set any container status to the empty address will also raise a #ValueError.

            >>> Address(":").set_container(True)
            Address(':')
            >>> Address(":").set_container(False)
            Traceback (most recent call last):
            ValueError: Cannot set container status to False for root address
            >>> Address("").set_container(True)
            Traceback (most recent call last):
            ValueError: Cannot set container status for empty address
        """

        if self.is_root():
            if not is_container:
                raise ValueError("Cannot set container status to False for root address")
            return self
        if self.is_empty():
            raise ValueError("Cannot set container status for empty address")
        return Address.create(self._is_absolute, is_container, self._elements)

    @property
    def name(self) -> str:
        """
        Returns the value of the last element in the Address. If the address has no elements, which is
        the case for the root address or an empty address, a #ValueError will be raised.

            >>> Address(":a:b").name
            'b'
            >>> Address("a:b?").name
            'b'
            >>> Address(":").name
            Traceback (most recent call last):
            ValueError: Address(':') has no elements, and thus no name
            >>> Address("").name
            Traceback (most recent call last):
            ValueError: Address('') has no elements, and thus no name
        """

        if not self._elements:
            raise ValueError(f"{self!r} has no elements, and thus no name")
        return self._elements[-1].value

    @property
    def elements(self) -> list[Element]:
        """
        Returns the individual elements of the address. Note that you should also check #is_absolute() to
        understand whether the elements are to be interpreted relative or absolute.

            >>> Address(":").elements
            []
            >>> Address(":a:b").elements
            [Address.Element(value='a', fallible=False), Address.Element(value='b', fallible=False)]
            >>> Address(":a:b").elements == Address("a:b").elements
            True
        """

        return self._elements

    @property
    def parent(self) -> Address:
        """
        Returns the parent address.

            >>> Address(":a:b").parent
            Address(':a')
            >>> Address(":a").parent
            Address(':')
            >>> Address("a").parent
            Address('.')
            >>> Address(".").parent
            Address('..')
            >>> Address("..").parent
            Address('..:..')

        The container status of the address is preserved.

            >>> Address(":a:b").parent
            Address(':a')
            >>> Address(":a:b:").parent
            Address(':a:')

        Use the `set_container()` method to change the container status.

        The root and empty address have no parent.

            >>> Address(":").parent
            Traceback (most recent call last):
            ValueError: Root address has no parent
            >>> Address("").parent
            Traceback (most recent call last):
            ValueError: Empty address has no parent
        """

        if self._is_absolute and not self._elements:
            raise ValueError("Root address has no parent")
        if not self._is_absolute and not self._elements:
            raise ValueError("Empty address has no parent")

        # When we currently have a relative address '.' we want to return '..'.
        if not self._is_absolute and self._elements and self._elements[-1].is_current():
            return Address.create(False, self._is_container, [Address.Element(Address.Element.PARENT, False)])

        # When we currently have a relative address '..' we want to return '..:..'
        if not self._is_absolute and self._elements and self._elements[-1].is_parent():
            return Address.create(
                False, self._is_container, self._elements + [Address.Element(Address.Element.PARENT, False)]
            )

        if not self._is_absolute and len(self._elements) == 1:
            return Address.CURRENT

        # Strip the last element.
        assert self._elements, self
        return Address.create(self._is_absolute, self._is_container, self._elements[:-1])

    Element: ClassVar[TypeAlias] = Element


Address.ROOT = Address(":")
Address.EMPTY = Address("")
Address.CURRENT = Address(".")
Address.PARENT = Address("..")
Address.WILDCARD = Address("*")
Address.RECURSIVE_WILDCARD = Address("**")
