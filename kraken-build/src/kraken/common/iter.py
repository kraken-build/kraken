from collections.abc import Iterable
from itertools import filterfalse, tee
from typing import Callable, TypeVar

T_co = TypeVar("T_co", covariant=True)


def bipartition(predicate: Callable[[T_co], bool], it: Iterable[T_co]) -> tuple[Iterable[T_co], Iterable[T_co]]:
    """
    Partition a stream into two separate streams based on a predicate.
    """

    t1, t2 = tee(it)
    return filterfalse(predicate, t1), filter(predicate, t2)
