from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kraken.core.address import Address

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
    def __init__(self, failed_tasks: Iterable[str]) -> None:
        self.failed_tasks = set(failed_tasks)

    def __repr__(self) -> str:
        if len(self.failed_tasks) == 1:
            return f'task "{next(iter(self.failed_tasks))}" failed'
        else:
            return "tasks " + ", ".join(f'"{task}"' for task in sorted(self.failed_tasks)) + " failed"
