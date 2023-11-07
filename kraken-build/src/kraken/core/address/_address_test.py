from __future__ import annotations

import dill  # type: ignore[import-untyped]
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


def test__Address__deserialization_is_consistent() -> None:
    """Tests whether a deserialized address has the same hash as the original one."""

    from kraken.core.address import Address

    addr = Address(":subproject:docker.build.linux-amd64")
    hash(addr)  # Make sure that the Address._hash_key attribute is initialized
    assert addr._hash_key is not None

    dumped = dill.dumps(addr)

    # We need to do some shenanigans to simulate the `dill` package deserializing the Address
    # object as if we were running in a new instance of the interpreter, i.e. with a different
    # instantiation of the module loaded from disk.
    #
    # However, we cannot just use `reload()` as that will have a permanent effect on other tests
    # and causing them to fail as some parts of the test reference the `Address` class from the
    # previous instance of the module, and some the new.
    #
    # The `localimport` module helps us to temporarily mess with the global interpreter module
    # state, and restore it after.

    from localimport import localimport

    with localimport("/i/dont/exist") as localimporter:
        localimporter.disable("kraken.core.address")
        from kraken.core.address import Address as AddressV2

        assert Address is not AddressV2

        loaded: Address = dill.loads(dumped)

    from kraken.core.address import Address as AddressSameAsV1

    assert Address is AddressSameAsV1

    # Sanity check, the types can't be the same after we reloaded the module. The __eq__() implementation
    # does an isinstance check for the other comparator, and so it will also fail.
    assert addr != loaded
    assert type(addr) is not type(loaded)
    # NOTE: We can't expect the hash to be consistent between runs of the Python interpreter.

    addr = AddressV2(str(addr))
    assert addr == loaded
    assert hash(addr) == hash(loaded)
    assert type(addr) is type(loaded)


def test__Address__deserialize_resets_cached_hash_key() -> None:
    """The Address class caches its own hash key on first request, this improves the hashing performance as the
    class is immutable. However, when deserializing the Address class, its hash may be different because of the
    Python interpreter hash salting and the `Address` class hash also being included in the instance hash."""

    addr = Address(":foo:bar")
    hash(addr)
    assert addr._hash_key is not None

    addr = dill.loads(dill.dumps(addr))
    assert addr._hash_key is None
