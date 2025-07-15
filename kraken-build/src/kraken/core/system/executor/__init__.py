"""Defines the Kraken executor API."""

from __future__ import annotations

import abc
from collections.abc import Iterator
from typing import TYPE_CHECKING

from kraken.core.address import Address

if TYPE_CHECKING:
    from kraken.core.system.task import Task, TaskStatus


class Graph(abc.ABC):
    """Interface for task graphs required for execution."""

    @abc.abstractmethod
    def ready(self) -> list[Task]:
        """Block until new tasks are ready to be executed. Return empty if no tasks are left. If no tasks are left
        but :meth:`is_complete` returns `False`, the build was unsuccessful."""

    @abc.abstractmethod
    def get_successors(self, task: Task) -> list[Task]:
        """Return all active dependants of the given task."""

    @abc.abstractmethod
    def get_task(self, task_path: Address) -> Task:
        """Return a task by its path."""

    @abc.abstractmethod
    def set_status(self, task: Task, status: TaskStatus) -> None:
        """Set the result of a task. Can be called twice for the same task unless the previous call was passing
        a status with type :attr:`TaskStatusType.STARTED`."""

    @abc.abstractmethod
    def is_complete(self) -> bool:
        """Return `True` if all tasks in the graph are done and successful."""

    @abc.abstractmethod
    def tasks(
        self,
        goals: bool = False,
        pending: bool = False,
        failed: bool = False,
        ok: bool = False,
        not_executed: bool = False,
    ) -> Iterator[Task]:
        """Returns the tasks in the graph in arbitrary order.

        :param goals: Return only goal tasks (i.e. leaf nodes).
        :param pending: Return only pending tasks.
        :param failed: Return only failed tasks.
        :param failed: Return only ok tasks.
        :param not_executed: Return only not executed tasks (i.e. downstream of failed tasks)"""

    @abc.abstractmethod
    def get_status(self, task: Task) -> TaskStatus | None: ...


class GraphExecutorObserver(abc.ABC):
    """Observes events in a Kraken task executor."""

    def before_execute_graph(self, graph: Graph) -> None: ...
    def before_prepare_task(self, task: Task) -> None: ...
    def after_prepare_task(self, task: Task, status: TaskStatus) -> None: ...
    def before_execute_task(self, task: Task, status: TaskStatus) -> None: ...
    def on_task_output(self, task: Task, chunk: bytes) -> None: ...
    def after_execute_task(self, task: Task, status: TaskStatus) -> None: ...
    def before_teardown_task(self, task: Task) -> None: ...
    def after_teardown_task(self, task: Task, status: TaskStatus) -> None: ...
    def after_execute_graph(self, graph: Graph) -> None: ...


class DelegatingGraphExecutorObserver(GraphExecutorObserver):
    """Delegates observer events to multiple observers in order."""

    def __init__(self, *delegates: GraphExecutorObserver) -> None:
        self.delegates = delegates

    def before_execute_graph(self, graph: Graph) -> None:
        """Invoke before_execute_graph on all delegates in order."""
        for delegate in self.delegates:
            delegate.before_execute_graph(graph)

    def before_prepare_task(self, task: Task) -> None:
        """Invoke before_prepare_task on all delegates in order."""
        for delegate in self.delegates:
            delegate.before_prepare_task(task)

    def after_prepare_task(self, task: Task, status: TaskStatus) -> None:
        """Invoke after_prepare_task on all delegates in order."""
        for delegate in self.delegates:
            delegate.after_prepare_task(task, status)

    def before_execute_task(self, task: Task, status: TaskStatus) -> None:
        """Invoke before_execute_task on all delegates in order."""
        for delegate in self.delegates:
            delegate.before_execute_task(task, status)

    def on_task_output(self, task: Task, chunk: bytes) -> None:
        """Invoke on_task_output on all delegates in order."""
        for delegate in self.delegates:
            delegate.on_task_output(task, chunk)

    def after_execute_task(self, task: Task, status: TaskStatus) -> None:
        """Invoke after_execute_task on all delegates in order."""
        for delegate in self.delegates:
            delegate.after_execute_task(task, status)

    def before_teardown_task(self, task: Task) -> None:
        """Invoke before_teardown_task on all delegates in order."""
        for delegate in self.delegates:
            delegate.before_teardown_task(task)

    def after_teardown_task(self, task: Task, status: TaskStatus) -> None:
        """Invoke after_teardown_task on all delegates in order."""
        for delegate in self.delegates:
            delegate.after_teardown_task(task, status)

    def after_execute_graph(self, graph: Graph) -> None:
        """Invoke after_execute_graph on all delegates in order."""
        for delegate in self.delegates:
            delegate.after_execute_graph(graph)


class GraphExecutor(abc.ABC):
    @abc.abstractmethod
    def execute_graph(self, graph: Graph, observer: GraphExecutorObserver) -> None: ...
