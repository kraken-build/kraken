from __future__ import annotations

from collections.abc import Collection

from kraken.common import Color
from kraken.common import colored as _colored
from kraken.core import Graph, Task, TaskGraph, TaskStatus, TaskStatusType
from kraken.core.system.executor.default import DefaultPrintingExecutorObserver

COLORS_BY_STATUS: dict[TaskStatusType, Color] = {
    TaskStatusType.PENDING: "magenta",
    TaskStatusType.FAILED: "red",
    TaskStatusType.INTERRUPTED: "red",
    TaskStatusType.SKIPPED: "yellow",
    TaskStatusType.WARNING: "yellow",
    TaskStatusType.SUCCEEDED: "green",
    TaskStatusType.STARTED: "magenta",
    TaskStatusType.UP_TO_DATE: "green",
}


def status_to_text(status: TaskStatus, colored: bool = True) -> str:
    if colored:
        message = _colored(status.type.name, COLORS_BY_STATUS.get(status.type))
    else:
        message = status.type.name
    if status.message:
        message += _colored(f" ({status.message})", "light_grey")
    return message


class ColoredDefaultPrintingExecutorObserver(DefaultPrintingExecutorObserver):
    def __init__(
        self,
        exclude_tasks: Collection[Task] | None = None,
        exclude_task_subgraphs: Collection[Task] | None = None,
    ) -> None:
        super().__init__(
            status_to_text=status_to_text,
            format_header=lambda s: _colored(s, "cyan", attrs=["bold", "underline"]),
            format_duration=lambda s: _colored(s, "cyan"),
        )
        self.exclude_tasks = exclude_tasks
        self.exclude_task_subgraphs = exclude_task_subgraphs

    def _mark_tasks_as_skipped(self, graph: TaskGraph, tasks: Collection[Task], recursive: bool = False) -> None:
        for task in tasks:
            if not graph.get_status(task):
                status = TaskStatus.skipped("excluded")
                graph.set_status(task, status)
                self.after_execute_task(task, status)
            if recursive:
                self._mark_tasks_as_skipped(graph, graph.get_predecessors(task, ignore_groups=False), recursive=True)

    # GraphExecutorObserver

    def before_execute_graph(self, graph: Graph) -> None:
        super().before_execute_graph(graph)
        assert isinstance(
            graph, TaskGraph
        ), f"{type(self).__name__} expected a TaskGraph instance, got {type(graph).__name__}"
        self._mark_tasks_as_skipped(graph, self.exclude_tasks or [])
        self._mark_tasks_as_skipped(graph, self.exclude_task_subgraphs or [], True)
