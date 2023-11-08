from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any, Generic, TypeVar

from ._address import Address
from ._addressable import Addressable

T_Addressable = TypeVar("T_Addressable", bound=Addressable)


class AddressSpace(ABC, Generic[T_Addressable]):
    """
    This is a base class to represent a space of #Addressable objects. Its methods must implement the navigation
    within that space per the elements in an #Address.

    See also: #resolve_address()
    """

    @abstractmethod
    def get_root(self) -> T_Addressable:
        """
        Returns the root node of the addressable space.
        """

        raise NotImplementedError(self)

    @abstractmethod
    def get_parent(self, entity: T_Addressable) -> T_Addressable | None:
        """
        Returns the parent of an addressable object.
        """

        raise NotImplementedError(self)

    @abstractmethod
    def get_children(self, entity: T_Addressable) -> Iterable[T_Addressable]:
        """
        Returns the children of an addressable object.
        """

        raise NotImplementedError(self)


@dataclass
class AddressResolutionStep(Generic[T_Addressable]):
    """
    A step in the address resolution. Each step represents the object and address at which the resolution
    continues to the next element of the address. When the last element of the address is reached, the
    #matches are filled.
    """

    #: The addressable object which served as the starting point for this step in the address resolution.
    entity: T_Addressable

    #: The remaining address that is resolved in this step in the context of #entity.
    query: Address

    #: A list of matches from the #entity that matched the #query. This is only filled if either the #query
    #: is the root address or a single element in the address remains; denoting the leaf and ultimate target
    #: of the query.
    #:
    #: See also: #is_leaf()
    matches: list[T_Addressable]

    #: A reference to the previous step in the resolution.
    previous_step: AddressResolutionStep[T_Addressable] | None = field(repr=False)

    #: A list of zero or more next steps in the resolution. This is only filled if the resolution step is not
    #: a leaf.
    #:
    #: See also: is_leaf()
    next_steps: list[AddressResolutionStep[T_Addressable]]

    def is_leaf(self) -> bool:
        """
        Returns `True` if the #query address indicates that this resolution step is a leaf step. The leaf
        step contains matching objects in the addressable space in #matches and contains no #next_steps.

        A leaf is indicated by the #query address either

        * being the root address (`:`), or
        * not being absolute and containing exactly one element (e.g. `a`, `.`, `**` and vice versa)

        >>> AddressResolutionStep(None, Address(":a"), [], None, []).is_leaf()
        False
        >>> AddressResolutionStep(None, Address("a"), [], None, []).is_leaf()
        True
        >>> AddressResolutionStep(None, Address("a:b"), [], None, []).is_leaf()
        False
        """

        return self.query.is_root() or (not self.query.is_absolute() and len(self.query) == 1)

    def is_concrete(self) -> bool:
        """
        Returns `True` if the resolution step is concrete and should thus have exactly one element in #matches (if
        the step is a leaf) or one element in #next_steps (if the step is not a leaf). A concrete step is one where

        * the #query address is either absolute (where the next steps or matches leads to the root of the addressable
          space), or
        * the first element is concrete (see #Address.Element.is_concrete()), or
        * the previous previous step was a recursive wildcard (`**`)

        >>> AddressResolutionStep(None, Address(":a?"), [], None, []).is_concrete()
        True
        >>> AddressResolutionStep(None, Address("a*"), [], None, []).is_concrete()
        False
        >>> AddressResolutionStep(None, Address("a:b?"), [], None, []).is_concrete()
        True
        >>> previous_step = AddressResolutionStep(None, Address("**"), [], None, [])
        >>> AddressResolutionStep(None, Address("b"), [], previous_step, []).is_concrete()
        False
        """

        if (
            self.previous_step
            and len(self.previous_step.query) > 0
            and self.previous_step.query[0].is_recursive_wildcard()
        ):
            return False

        return self.query.is_absolute() or bool(self.query and self.query[0].is_concrete())


@dataclass
class AddressResolutionResult(Generic[T_Addressable]):
    """
    A wrapper for the resolution of address resolution using #resolve_address().

    In addition to containing a reference to the initial resolution step in #root, it provides
    utility methods for working with the resulting tree.
    """

    space: AddressSpace[T_Addressable]
    root: AddressResolutionStep[T_Addressable]

    def all_steps(self) -> Iterable[AddressResolutionStep[T_Addressable]]:
        """
        Returns a generator that iterates over all resolution steps.
        """

        def generator(step: AddressResolutionStep[T_Addressable]) -> Iterable[AddressResolutionStep[T_Addressable]]:
            yield step
            for next_step in step.next_steps:
                yield from generator(next_step)

        return generator(self.root)

    def matches(self) -> Iterable[T_Addressable]:
        """
        Returns all #AddressResolutionStep.matches from all steps in the tree.
        """

        for step in self.all_steps():
            yield from step.matches


def resolve_address(
    space: AddressSpace[T_Addressable],
    entity: T_Addressable,
    query: Address,
) -> AddressResolutionResult[T_Addressable]:
    """
    Resolves an address in any address *space*, starting from any addressable object in that space *entity* to
    find zero or more related entities in the same space by following the specified *query* address.

    In essence, this function follows the address elements in the *query* starting from *entity* and returns the
    matching entities.

    >>> from ._address_resolver_test import Node, NodeAddressSpace
    >>> root = Node(None, "root")
    >>> a = Node(root, "a")
    >>> aa = Node(a, "a")
    >>> c = Node(root, "c")
    >>> ca = Node(c, "a")
    >>> space = NodeAddressSpace(root)
    >>>
    >>> list(resolve_address(space, aa, Address(":a")).matches())
    [Node(address=Address(':a'))]
    >>> list(resolve_address(space, c, Address(":a:a")).matches())
    [Node(address=Address(':a:a'))]
    >>> list(resolve_address(space, c, Address("..:a")).matches())
    [Node(address=Address(':a'))]
    >>> list(resolve_address(space, root, Address("*:a")).matches())
    [Node(address=Address(':a:a')), Node(address=Address(':c:a'))]
    >>> list(resolve_address(space, root, Address("d?")).matches())
    []

    When an address cannot be resolved, you get an #AddressResolutionError.

    >>> resolve_address(space, root, Address("d")) # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    kraken.core.address._address_resolver.AddressResolutionError: Could not resolve address 'd' in context \
':'. The failure occurred at address ':' trying to resolve the remainder 'd'. The address ':d' does not exist.

    Recursive wildcards expect to find at least one match on the next element, unless that element is fallible:

    >>> list(resolve_address(space, root, Address("**:c")).matches())
    [Node(address=Address(':c'))]
    >>> resolve_address(space, root, Address("**:d")) # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    kraken.core.address._address_resolver.AddressResolutionError: Could not resolve address '**:d' in context \
':'. The failure occurred at address ':' trying to resolve the remainder '**:d'. The address ':**:d' does not exist.
    >>> list(resolve_address(space, root, Address("**:d?")).matches())
    []
    """

    root_entity = entity
    root_query = query

    if query.is_empty():
        raise ValueError("An empty address query cannot be resolved")

    def recurse_tree(entity: T_Addressable, include_root: bool = True) -> Iterable[T_Addressable]:
        if include_root:
            yield entity
        for child in space.get_children(entity):
            yield from recurse_tree(child)

    def has_children(
        space: AddressSpace[T_Addressable],
        addr: T_Addressable,
    ) -> bool:
        return any(True for _ in space.get_children(addr))

    def resolve_step(
        previous_step: AddressResolutionStep[T_Addressable] | None,
        entity: T_Addressable,
        query: Address,
        restrict_to_containers: bool = False,
    ) -> AddressResolutionStep[T_Addressable]:
        assert not query.is_empty()

        current_step = AddressResolutionStep[T_Addressable](
            entity=entity,
            query=query,
            matches=[],
            previous_step=previous_step,
            next_steps=[],
        )

        if query.is_absolute():
            element = None
            next_entities = [space.get_root()]
            if len(query.elements) == 0:
                remainder = None
            else:
                remainder = Address.create(False, query.is_container(), query.elements)
        else:
            element = query.elements[0]
            if len(query.elements) > 1:
                remainder = Address.create(query.is_absolute(), query.is_container(), query.elements[1:])
            else:
                remainder = Address("")
            if element.is_current():
                next_entities = [entity]
            elif element.is_parent():
                next_entities = list(filter(None, (space.get_parent(entity),)))
            elif element.is_recursive_wildcard():
                # TODO(NiklasRosenstein): We might want to keep the generator here for perf/mem.
                # NOTE: When we have no more elements to resolve following the recursive wildcard, we don't
                #   want the result here to include the current entity (e.g. `:a:**` should not include `:a`).
                next_entities = list(recurse_tree(entity, include_root=not remainder.is_empty()))
            else:
                next_entities = [
                    x  # linebreak for formatting
                    for x in space.get_children(entity)
                    if fnmatch(x.address.name, element.value)
                ]

        # Check if the resolution for this step failed. Only when the step was resolving a concrete element
        # of the address can the resolution fail. If the previous element was a recursive wildcard (`**`) or if
        # the current element is fallible (`a?`) then we permit no results.
        if current_step.is_concrete() and not next_entities:
            raise AddressResolutionError(space, root_entity, root_query, entity, query)

        if not remainder:
            # There are no more elements to continue branching the address resolution for.
            if restrict_to_containers:
                current_step.matches += [node for node in next_entities if has_children(space, node)]
            else:
                current_step.matches += next_entities
        else:
            # There are elements to continue the address resolution for.
            for next_entity in next_entities:
                next_step = resolve_step(current_step, next_entity, remainder, restrict_to_containers)
                current_step.next_steps.append(next_step)

            # If the current element is a recursive wildcard, and the next element is not fallible, we require
            # that at least one matching element was found in the next steps of the resolution.
            if not remainder[-1].fallible and element and element.is_recursive_wildcard():
                if not any(s.next_steps or s.matches for s in current_step.next_steps):
                    raise AddressResolutionError(space, root_entity, root_query, entity, query)

        return current_step

    restrict_to_containers = query.is_container()
    return AddressResolutionResult(space=space, root=resolve_step(None, entity, query, restrict_to_containers))


@dataclass
class AddressResolutionError(Exception):
    """
    This exception is raised by #resolve_address() if a concrete resolution step failed.
    """

    space: AddressSpace[Any]
    entity: Addressable
    query: Address
    failed_at: Addressable
    remainder: Address

    def is_recursive_wildcard_failure(self) -> bool:
        """
        Returns `True` if this error is caused by a failure to resolve at least one member of a recursive wildcard
        element in the address. This is the case when the #remainder's first element is a recursive wildcard. Recursive
        wildcards themselves cannot fail to resolve, but only their immediate following element.

        For example, when `Address(":**:d")` is resolved and no `d` exists, then this method returns `True` for
        the exception that is raised by #resolve_address().
        """

        return len(self.remainder) > 0 and self.remainder[0].is_recursive_wildcard()

    def get_nonexistent_address(self) -> Address:
        """
        Calculates the absolute address that does not exist to illustrate the point of failure in the address
        resolution. For failures to resolve the next element of a recursive wildcard, this will return the
        address including the wildcard, e.g. `:**:d` would indicate that in the entire address space there exists
        not a single addressable object where the #Address.name is `d`.
        """

        shift = 1 if self.is_recursive_wildcard_failure() else 0
        clipped = Address.create(
            self.remainder.is_absolute(),
            self.remainder.is_container(),
            self.remainder.elements[: shift + int(not self.remainder.is_absolute())],
        )
        return self.failed_at.address.concat(clipped)

    def __str__(self) -> str:
        return (
            f"Could not resolve address '{self.query}' in context '{self.entity.address}'. "
            f"The failure occurred at address '{self.failed_at.address}' trying to resolve the remainder "
            f"'{self.remainder}'. The address '{self.get_nonexistent_address()}' does not exist."
        )
