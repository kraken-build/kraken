from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kraken.core.address import Address
    from kraken.core.system.task import Task

    from .project import Project


class ProjectNotFoundError(Exception):
    def __init__(self, address: Address) -> None:
        self.address = address

    def __str__(self) -> str:
        return f"project not found: {self.address}"


class ProjectLoaderError(Exception):
    def __init__(self, project: Project, message: str) -> None:
        self.project = project
        self.message = message

    def __str__(self) -> str:
        return f"[{self.project.address}] {self.message}"


class BuildError(Exception):
    def __init__(self, failed_tasks: Iterable[Task], reason: str | None = None) -> None:
        assert not isinstance(failed_tasks, str), type(failed_tasks)  # type: ignore[unreachable]
        assert isinstance(failed_tasks, Iterable), type(failed_tasks)
        self.failed_tasks = set(failed_tasks)
        self.reason = reason

    def __str__(self) -> str:
        if len(self.failed_tasks) == 1:
            result = f'task "{next(iter(self.failed_tasks)).address}" failed'
        else:
            result = (
                "tasks "
                + ", ".join(f'"{task}"' for task in sorted(str(x.address) for x in self.failed_tasks))
                + " failed"
            )
        if self.reason:
            result = f"{result}\nreason: {self.reason}"
        return result
