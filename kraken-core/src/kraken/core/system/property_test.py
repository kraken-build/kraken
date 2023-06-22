from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from pytest import mark, raises
from typing_extensions import Literal

from kraken.core.system.property import Property, PropertyContainer


def test__Property_value_adapter_order_is_semantically_revelant() -> None:
    """Tests that a `str | Path` and `Path | str` property behave differently."""

    prop1: Property[Union[str, Path]] = Property(PropertyContainer(), "prop1", Union[str, Path])
    prop1.set("foo/bar")
    assert prop1.get() == "foo/bar"

    prop2: Property[Union[Path, str]] = Property(PropertyContainer(), "prop2", Union[Path, str])
    prop2.set("foo/bar")
    assert prop2.get() == Path("foo/bar")

    prop2.setmap(lambda s: Path(str(s).upper()))
    assert prop2.get() == Path("FOO/BAR")


def test__Property_default() -> None:
    """Tests that property defaults work as expected."""

    a_value = ["abc"]

    class MyObj(PropertyContainer):
        a: Property[List[str]] = Property.config(default=a_value)
        b: Property[int] = Property.config(default_factory=lambda: 42)
        c: Property[str]

    obj = MyObj()
    assert obj.a.get() == a_value
    assert obj.a.get() is not a_value  # Copied
    assert obj.b.get() == 42
    assert obj.c.is_empty()


def test__Property_default_factory_with_subclass() -> None:
    """Tests that property default factory works with a subclass (a known previous semantic failure case)."""

    class MyObj(PropertyContainer):
        b: Property[Dict[str, str]] = Property.default_factory(dict)

    class SubObj(MyObj):
        pass

    obj = MyObj()
    assert obj.b.get() == {}

    subobj = SubObj()
    assert subobj.b.get() == {}


def test__Property__provides() -> None:
    assert Property[str](PropertyContainer(), "foo", str).provides(str)
    assert not Property[Path](PropertyContainer(), "foo", Path).provides(str)
    assert Property[Union[str, Path]](PropertyContainer(), "foo", Union[str, Path]).provides(str)
    assert Property[Union[str, Path]](PropertyContainer(), "foo", Union[str, Path]).provides(Path)
    assert not Property[Union[str, Path]](PropertyContainer(), "foo", Union[str, Path]).provides(int)
    assert not Property[Union[str, Path]](PropertyContainer(), "foo", Union[str, Path]).provides(type(None))
    assert Property[Optional[str]](PropertyContainer(), "foo", Optional[str]).provides(str)
    assert Property[Optional[str]](PropertyContainer(), "foo", Optional[str]).provides(type(None))


def test__Property__get_of_type__scalar() -> None:
    p1 = Property[str](PropertyContainer(), "foo", str)
    p1.set("bar")
    assert p1.get_of_type(str) == ["bar"]


def test__Property__get_of_type__scalar_no_match() -> None:
    p1 = Property[str](PropertyContainer(), "foo", str)
    p1.set("bar")
    assert p1.get_of_type(int) == []


def test__Property__get_of_type__sequence() -> None:
    p1 = Property[List[str]](PropertyContainer(), "foo", List[str])
    p1.set(["hello", "world"])
    assert p1.get_of_type(str) == ["hello", "world"]


def test__Property__get_of_type__sequence_no_match() -> None:
    p1 = Property[List[str]](PropertyContainer(), "foo", List[str])
    p1.set(["hello", "world"])
    assert p1.get_of_type(int) == []


def test__Property__get_of_type__sequence_partial_match() -> None:
    p1 = Property[List[Union[str, int]]](PropertyContainer(), "foo", List[Union[str, int]])
    p1.set(["hello", 42, "world"])
    assert p1.get_of_type(int) == [42]
    assert p1.get_of_type(str) == ["hello", "world"]
    assert p1.get_of_type(object) == ["hello", 42, "world"]
    assert p1.get_of_type(type(None)) == []
    assert p1.get_of_type(list) == [["hello", 42, "world"]]


def test__Property__deferred_exception_propagates() -> None:
    p1 = Property[str](PropertyContainer(), "foo", str)
    p2 = Property[str](PropertyContainer(), "bar", str, deferred=True)

    with raises(Property.Empty):
        p1.get()
    with raises(Property.Deferred):
        p2.get()

    p1.set(p2)
    with raises(Property.Deferred):
        p1.get()

    p2.set("hello")
    assert p1.get() == "hello"


def test__Property__deferred_registers_as_empty() -> None:
    p1 = Property[str](PropertyContainer(), "foo", str, deferred=True)
    assert p1.is_empty()
    assert not p1.is_filled()


def test__Property__property_pointing_to_a_deferred_property_does_not_register_as_empty() -> None:
    """
    A property that is populated with the value of another Property that is deferred should not register as empty,
    instead it should propagate the deferred exception.
    """

    p1 = Property[str](PropertyContainer(), "foo", str, deferred=True)
    p2 = Property[str](PropertyContainer(), "bar", str)

    p2.set(p1)
    with raises(Property.Deferred):
        p2.is_empty()

    p1.set("hello")
    assert not p2.is_empty()
    assert p2.is_filled()


def test__Property__accepts_tuple() -> None:
    p1 = Property[Tuple[str, int]](PropertyContainer(), "foo", Tuple[str, int])
    p1.set(("hello", 42))
    assert p1.get() == ("hello", 42)
    with raises(TypeError):
        p1.set(["hello", 42])  # type: ignore[arg-type]


@mark.skip(reason="we don't currently do this level of validaton")
def test__Property__does_not_accept_tuple_with_wrong_type() -> None:
    p1 = Property[Tuple[str, int]](PropertyContainer(), "foo", Tuple[str, int])
    with raises(TypeError):
        p1.set(("hello", "world"))  # type: ignore[arg-type]


def test__Property__does_accept_literal_type_hint() -> None:
    prop = Property[Literal["foo", "bar"]](PropertyContainer(), "foo", Literal["foo", "bar"])
    prop.set("foo")
    prop.set("bar")

    # Cannot set int when only string literals are accepted.
    with raises(TypeError) as excinfo:
        prop.set(42)  # type: ignore[arg-type]
    assert str(excinfo.value).endswith("expected str, got int")

    # Cannot set a string literal that is not in the list of accepted literals.
    # This is because we don't currently validate the values.
    # TODO(@NiklasRosenstein): Validate Literal values.
    prop.set("bazinga")


def test__PropertyContainer__output_property_is_deferred_by_default() -> None:
    class MyObj(PropertyContainer):
        a: Property[str]
        b: Property[str] = Property.output()

    obj = MyObj()
    with raises(Property.Empty):
        obj.a.get()
    with raises(Property.Deferred):
        obj.b.get()

    obj.a.set("foo")
    assert obj.a.get() == "foo"
    obj.b.set("bar")
    assert obj.b.get() == "bar"
