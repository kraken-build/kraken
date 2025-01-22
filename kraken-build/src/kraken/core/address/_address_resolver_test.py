from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pytest import raises

from kraken.core.address import Address, AddressResolutionError, AddressSpace, resolve_address


@dataclass(init=False, repr=False)
class Node:
    parent: Node | None
    address: Address
    children: dict[str, Node]

    def __init__(self, parent: Node | None, name: str) -> None:
        self.parent = parent
        self.address = parent.address.append(name) if parent else Address.ROOT
        self.children = {}
        if parent:
            assert name not in parent.children, self.address
            parent.children[name] = self

    def __repr__(self) -> str:
        return f"Node(address={self.address!r})"


class NodeAddressSpace(AddressSpace[Node]):
    def __init__(self, root: Node) -> None:
        self._root = root

    def get_root(self) -> Node:
        return self._root

    def get_parent(self, entity: Node) -> Node | None:
        return entity.parent

    def get_children(self, entity: Node) -> Iterable[Node]:
        return entity.children.values()


class ExampleNodeTree:
    """Builds an example node tree."""

    def __init__(self) -> None:
        self.root = Node(None, "<root>")
        self.a = Node(self.root, "a")
        self.aa = Node(self.a, "a")
        self.ab = Node(self.a, "b")
        self.aba = Node(self.ab, "a")
        self.abb = Node(self.ab, "b")
        self.abc = Node(self.ab, "c")
        self.d = Node(self.root, "d")


def test__resolve_address__can_resolve_concrete_addresses() -> None:
    tree = ExampleNodeTree()
    space = NodeAddressSpace(tree.root)

    with raises(ValueError) as excinfo:
        resolve_address(space, tree.root, Address(""))
    assert str(excinfo.value) == "An empty address query cannot be resolved"

    assert list(resolve_address(space, tree.root, Address(":")).matches()) == [tree.root]
    assert list(resolve_address(space, tree.root, Address(":a")).matches()) == [tree.a]
    assert list(resolve_address(space, tree.root, Address(":a:b")).matches()) == [tree.ab]
    assert list(resolve_address(space, tree.root, Address(":a:b:a")).matches()) == [tree.aba]
    assert list(resolve_address(space, tree.root, Address(":a:b:c")).matches()) == [tree.abc]
    assert list(resolve_address(space, tree.root, Address(":d")).matches()) == [tree.d]
    assert list(resolve_address(space, tree.root, Address("d")).matches()) == [tree.d]
    assert list(resolve_address(space, tree.a, Address("..")).matches()) == [tree.root]
    assert list(resolve_address(space, tree.aa, Address("..:b")).matches()) == [tree.ab]
    assert list(resolve_address(space, tree.root, Address(":**:a")).matches()) == [tree.a, tree.aa, tree.aba]
    assert list(resolve_address(space, tree.root, Address(":**")).matches()) == [
        tree.a,
        tree.aa,
        tree.ab,
        tree.aba,
        tree.abb,
        tree.abc,
        tree.d,
    ]
    assert list(resolve_address(space, tree.root, Address(":**:")).matches()) == [tree.a, tree.ab]


def test__resolve_address__does_not_resolve_missing_address_and_raises_error() -> None:
    tree = ExampleNodeTree()
    space = NodeAddressSpace(tree.root)

    with raises(AddressResolutionError) as excinfo:
        resolve_address(space, tree.root, Address("a:c"))
    assert excinfo.value == AddressResolutionError(space, tree.root, Address("a:c"), tree.a, Address("c"))
    assert str(excinfo.value) == (
        "Could not resolve address 'a:c' in context ':'. The failure occurred at address "
        "':a' trying to resolve the remainder 'c'. The address ':a:c' does not exist."
    )


def test__resolve_address__can_resolve_wildcards() -> None:
    tree = ExampleNodeTree()
    space = NodeAddressSpace(tree.root)

    assert list(resolve_address(space, tree.root, Address("*")).matches()) == [tree.a, tree.d]
    assert list(resolve_address(space, tree.root, Address(":a:b:*")).matches()) == [tree.aba, tree.abb, tree.abc]


def test__resolve_address__can_resolve_recursive_wildcards() -> None:
    tree = ExampleNodeTree()
    space = NodeAddressSpace(tree.root)

    assert list(resolve_address(space, tree.root, Address(":a:**")).matches()) == [
        tree.aa,
        tree.ab,
        tree.aba,
        tree.abb,
        tree.abc,
    ]
    assert list(resolve_address(space, tree.root, Address(":a:b:**")).matches()) == [tree.aba, tree.abb, tree.abc]
    assert list(resolve_address(space, tree.root, Address(":**:a")).matches()) == [tree.a, tree.aa, tree.aba]


def test__resolve_address__does_not_fail_on_optional_element() -> None:
    tree = ExampleNodeTree()
    space = NodeAddressSpace(tree.root)

    # We can sucessfully resolve :a:b? to :a:b.
    assert list(resolve_address(space, tree.root, Address(":a:b?")).matches()) == [tree.ab]

    # We can sucessfully resolve :a:dontexist? to nothing, as the address does not exist.
    assert list(resolve_address(space, tree.root, Address(":a:dontexist?")).matches()) == []

    # Try to resolve :a:dontexist without an optional element fails.
    with raises(AddressResolutionError):
        list(resolve_address(space, tree.root, Address(":a:dontexist")).matches())

    # We can sucessfully resolve :a:b?:a to :a:b:a.
    assert list(resolve_address(space, tree.root, Address(":a:b?:a")).matches()) == [tree.aba]

    # We can sucessfully resolve :a:b?:dontexist to nothing, as the element that does not exist is optional.
    assert list(resolve_address(space, tree.root, Address(":a:b:dontexist?")).matches()) == []

    # It is also okay to resolve :a::missing1?:missing to nothing, because we won't try to look up the missing2
    # on missing1, since missing1 doesn't exist in the first place.
    assert list(resolve_address(space, tree.root, Address(":a:missing1?:missing2")).matches()) == []

    # However, trying to lookup a non-optional missing element on an optional but existing element fails.
    with raises(AddressResolutionError):
        list(resolve_address(space, tree.root, Address(":a:b?:dontexist")).matches())
