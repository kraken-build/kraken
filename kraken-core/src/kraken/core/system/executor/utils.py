from __future__ import annotations

import threading
from typing import NamedTuple

from kraken.core.system.task import Task


class TaskRememberer:
    """Remembers tasks that have been executed but need to be torn down when all their dependants are done.

    This class is thread safe."""

    class _RememberedTask(NamedTuple):
        task: Task
        dependants: set[Task]

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._remembered: list[TaskRememberer._RememberedTask] = []

    def remember(self, task: Task, dependants: set[Task]) -> None:
        """Remember that *task* needs to be torn down if all *dependants* are done."""

        with self._lock:
            self._remembered.append(self._RememberedTask(task, dependants))

    def done(self, task: Task) -> list[Task]:
        """Mark the given *task* as done and return all remembered tasks which no longer have not-done dependants.ß"""

        with self._lock:
            ready, remember = [], []
            for dependency, dependants in self._remembered:
                dependants.discard(task)
                if not dependants:
                    ready.append(dependency)
                else:
                    remember.append(self._RememberedTask(dependency, dependants))
            self._remembered = remember

        return ready

    def forget_all(self) -> list[Task]:
        """Forget all tasks currently remembered."""

        tasks = [x.task for x in self._remembered]
        self._remembered.clear()
        return tasks
