from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from kraken.common import Supplier

__all__ = ["TaskSupplier"]

if TYPE_CHECKING:
    from kraken.core.system.task import Task


class TaskSupplier(Supplier["Task"]):
    """Internal. This is a helper class that allows us to represent a dependency on a task in the lineage of a property
    without including an actual property of that task in it. This is a bit of a hack because the
    :meth:`Supplier.derived_from()` API only allows to return more suppliers."""

    def __init__(self, task: Task) -> None:
        self._task = task

    def get(self) -> Task:
        return self._task

    def derived_from(self) -> Iterable[Supplier[Any]]:
        return ()
