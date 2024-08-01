from collections.abc import Iterable
from itertools import filterfalse, tee
from typing import Callable, TypeVar

T_co = TypeVar("T_co", covariant=True)


def bipartition(predicate: Callable[[T_co], bool], it: Iterable[T_co]) -> tuple[Iterable[T_co], Iterable[T_co]]:
    """
    Partition a stream into two separate streams based on a predicate.

    Returns:
        A tuple of two iterators, where the first iterator contains only the elements for which the *predicate*
        returned `False`, and the second iterator contains only the elements for which it returned `True`.
    """

    t1, t2 = tee(it)
    return filterfalse(predicate, t1), filter(predicate, t2)
