from __future__ import annotations

from pytest import raises

from kraken.core.address import Address


def test__Address__reuse() -> None:
    a1 = Address(":a:b")
    assert a1 is Address(a1)
    assert a1 is not Address(":a:b")


def test__Address__parse_empty_address() -> None:
    assert not Address("").is_absolute()
    assert Address("").elements == []
    assert str(Address("")) == ""


def test__Address__parse_root_address() -> None:
    assert Address(":").is_absolute()
    assert Address(":").elements == []
    assert Address(":").is_root()
    assert str(Address(":")) == ":"


def test__Address__parse_container_address() -> None:
    assert Address(":") == Address.ROOT
    assert Address(":").is_absolute()
    assert Address(":").is_container()

    assert Address(".") == Address.CURRENT
    assert not Address(".").is_absolute()
    assert not Address(".").is_container()
    assert Address(".:").is_container()

    # Absolute / Not Container
    assert Address(":a:b").is_absolute()
    assert not Address(":a:b").is_container()

    # Absolute / Container
    assert Address(":a:b:").is_absolute()
    assert Address(":a:b:").is_container()

    # Relative / Not Container
    assert not Address("a:b").is_absolute()
    assert not Address("a:b").is_container()

    # Relative / Container
    assert not Address("a:b:").is_absolute()
    assert Address("a:b:").is_container()

    assert Address(":a:..").normalize() == Address(":")
    assert Address("a:..:").normalize() == Address(".")


def test__Address__str() -> None:
    assert str(Address(":a")) == ":a"
    assert str(Address(":a:..:b")) == ":a:..:b"
    assert str(Address(":a?:c")) == ":a?:c"
    assert str(Address("a?:..")) == "a?:.."
    assert str(Address(":**:foo")) == ":**:foo"
    assert str(Address(":")) == ":"


def test__Address__cannot_contain_empty_element() -> None:
    with raises(ValueError):
        Address(":a::b")


def test__Address__cannot_contain_non_ascii_characters() -> None:
    with raises(ValueError):
        Address(":a:Ö")


def test__Address__concat() -> None:
    assert Address(".").concat("foo:bar") == Address(".:foo:bar")
    assert Address(":").concat("foo:bar") == Address(":foo:bar")
    assert Address("a:b").concat(":c") == Address(":c")

    assert str(Address(":a:").concat("b")) == ":a:b"
    assert str(Address(":a").concat("b:")) == ":a:b:"


def test__Address__normalize() -> None:
    assert Address("foo:..").normalize() == Address(".")
    assert Address("foo:bar:..").normalize() == Address("foo")
    assert Address(".:foo:bar").normalize() == Address("foo:bar")
    assert Address(".").normalize() == Address(".")
    assert Address("..").normalize() == Address("..")
    assert Address(":").normalize() == Address(":")
    assert Address(":..").normalize() == Address(":..")
    assert Address(":foo:bar:..").normalize() == Address(":foo")
    assert Address("b:..:a:..").normalize() == Address(".")
    assert Address(":b:..:a:..").normalize() == Address(":")
    assert Address(":**:a").normalize() == Address(":**:a")


def test__Address__parent_raises_ValueError_on_root() -> None:
    with raises(ValueError) as excinfo:
        Address(":").parent
    assert str(excinfo.value) == "Root address has no parent"


def test__Address__parent() -> None:
    assert Address(":a:b").parent == Address(":a")
    assert Address(":a:b").parent != Address(":a:")
    assert Address(".").parent == Address("..")
    assert Address("..").parent == Address("..:..")
    assert Address("..:a").parent == Address("..")
    assert Address("b:..:a").parent == Address("b:..")
    assert Address("b:..").parent == Address("b:..:..")


def test__Address__set_container() -> None:
    assert Address(":a:b").set_container(True) == Address(":a:b:")
    assert Address(":a:b:").set_container(True) == Address(":a:b:")
    assert Address(":a:b:").set_container(False) == Address(":a:b")
    assert Address(":a:..").set_container(False) == Address(":a:..")
    assert Address(":a:..:").set_container(True) == Address(":a:..:")
    assert Address(":a:..:").set_container(False) == Address(":a:..")
