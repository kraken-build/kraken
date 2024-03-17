from __future__ import annotations

import abc
import sys
import threading
import time
import traceback
from collections.abc import Callable, Iterable
from functools import partial

from kraken.core.address import Address
from kraken.core.system.executor import Graph, GraphExecutor, GraphExecutorObserver
from kraken.core.system.executor.utils import TaskRememberer
from kraken.core.system.task import GroupTask, Task, TaskStatus, VoidTask

TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE = "Tasks that were not executed due to failing dependencies"


class TaskExecutor(abc.ABC):
    @abc.abstractmethod
    def execute_task(self, task: Task, done: Callable[[TaskStatus], None]) -> None: ...

    @abc.abstractmethod
    def teardown_task(self, task: Task, done: Callable[[TaskStatus], None]) -> None: ...


class DefaultTaskExecutor(TaskExecutor):
    """The most straight forward task executor."""

    def _call(self, func: Callable[[], TaskStatus | None]) -> TaskStatus:
        try:
            status = func()
            if status is None:
                return TaskStatus.succeeded()
            elif not isinstance(status, TaskStatus):
                return TaskStatus.failed(f"bad status: {status!r}")  # type: ignore[unreachable]
            return status
        except KeyboardInterrupt:
            return TaskStatus.interrupted()
        except BaseException as exc:
            traceback.print_exc()
            return TaskStatus.failed(f"unhandled exception: {exc}")

    def execute_task(self, task: Task, done: Callable[[TaskStatus], None]) -> None:
        if any(task.get_tags("skip")):
            raise RuntimeError(f"Tasks that are set to be skipped must not be passed into the task executor: {task!r}")
        done(self._call(task.execute))

    def teardown_task(self, task: Task, done: Callable[[TaskStatus], None]) -> None:
        done(self._call(task.teardown))


class DefaultGraphExecutor(GraphExecutor):
    """The most straight forward graph executor."""

    def __init__(self, task_executor: TaskExecutor) -> None:
        self._task_executor = task_executor

    def execute_graph(self, graph: Graph, observer: GraphExecutorObserver) -> None:
        remember = TaskRememberer()
        interrupted = False

        def invoke_execute(tasks: Iterable[Task]) -> None:
            for task in tasks:
                if interrupted:
                    break

                skip_tags = task.get_tags("skip")
                if skip_tags:
                    status = TaskStatus.skipped("; ".join(t.reason for t in skip_tags))
                else:
                    observer.before_prepare_task(task)
                    status = task.prepare() or TaskStatus.pending()
                    observer.after_prepare_task(task, status)
                    if status.is_pending():
                        observer.before_execute_task(task, status)
                        self._task_executor.execute_task(task, partial(execute_done, task))
                        continue  # Don't call execute_done here

                execute_done(task, status)

        def invoke_teardown(tasks: Iterable[Task]) -> None:
            for task in tasks:
                observer.before_teardown_task(task)
                self._task_executor.teardown_task(task, partial(teardown_done, task))

        def execute_done(task: Task, status: TaskStatus) -> None:
            nonlocal interrupted
            graph.set_status(task, status)
            observer.after_execute_task(task, status)
            if status.is_started():
                # NOTE (@NiklasRosenstein): (untested hyopthesis) If we do not call remember.done(task) here, it means
                #       that a started task that depends on another started task will not end unless the second started
                #       task is done. This could be desirable behaviour.
                remember.remember(task, set(graph.get_successors(task)))
            else:
                if status.is_interrupted():
                    interrupted = True
                invoke_teardown(remember.done(task))

        def teardown_done(task: Task, status: TaskStatus) -> None:
            nonlocal interrupted
            if status.is_interrupted():
                interrupted = True
            graph.set_status(task, status)
            observer.after_teardown_task(task, status)
            invoke_teardown(remember.done(task))

        observer.before_execute_graph(graph)

        try:
            while not graph.is_complete() and not interrupted:
                tasks = graph.ready()
                if not tasks:
                    break
                invoke_execute(tasks)
        finally:
            invoke_teardown(remember.forget_all())
            observer.after_execute_graph(graph)


class DefaultPrintingExecutorObserver(GraphExecutorObserver):
    """The default printing executor that has some parameters for customization."""

    def __init__(
        self,
        execute_prefix: str = ">",
        teardown_prefix: str = "X",
        status_to_text: Callable[[TaskStatus], str] | None = None,
        format_header: Callable[[str], str] | None = None,
        format_duration: Callable[[str], str] | None = None,
    ) -> None:
        self.execute_prefix = execute_prefix
        self.teardown_prefix = teardown_prefix
        self.status_to_text = status_to_text or self.default_status_to_text
        self.format_header = format_header or str
        self.format_duration = format_duration or str
        self._lock = threading.Lock()
        self._status: dict[Address, TaskStatus] = {}
        self._started: dict[Address, float] = {}
        self._duration: dict[Address, float] = {}

    def _ask_report_task_status(self, task: Task, status: TaskStatus) -> bool:
        return not (isinstance(task, (GroupTask, VoidTask)) and status.is_skipped())

    def before_execute_graph(self, graph: Graph) -> None:
        print(flush=True)
        print(self.format_header("Start build"), flush=True)
        print(flush=True)

    def after_execute_graph(self, graph: Graph) -> None:
        print(flush=True)
        print(self.format_header("Build summary"), flush=True)
        print(flush=True)

        for task_addr, status in self._status.items():
            task = graph.get_task(task_addr)
            if self._ask_report_task_status(task, status):
                print(
                    " " * (len(self.execute_prefix) + 1) + str(task_addr),
                    self.status_to_text(status),
                    self.format_duration(f"[{self._duration[task_addr]:.3f}s]") if task_addr in self._duration else "",
                )

        not_executed_tasks = [t for t in graph.tasks(not_executed=True) if not isinstance(t, GroupTask)]
        if len(not_executed_tasks) != 0:
            print(flush=True)
            print(self.format_header(TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE), flush=True)
            print(flush=True)
            for task in not_executed_tasks:
                print(" " * (len(self.execute_prefix) + 1) + str(task.address))
        print(flush=True)

    def default_status_to_text(self, status: TaskStatus) -> str:
        if status.message:
            return f"{status.type.name} ({status.message})"
        else:
            return status.type.name

    def before_execute_task(self, task: Task, status: TaskStatus) -> None:
        print(self.execute_prefix, task.address, self.status_to_text(status), flush=True)
        with self._lock:
            self._started[task.address] = time.perf_counter()

    def on_task_output(self, task: Task, chunk: bytes) -> None:
        sys.stdout.buffer.write(chunk)
        sys.stdout.flush()

    def after_execute_task(self, task: Task, status: TaskStatus) -> None:
        if self._ask_report_task_status(task, status):
            print(self.execute_prefix, task.address, self.status_to_text(status), flush=True)
        with self._lock:
            self._status[task.address] = status
            if task.address in self._started:
                self._duration[task.address] = time.perf_counter() - self._started[task.address]

    def before_teardown_task(self, task: Task) -> None:
        print(self.teardown_prefix, task.address, flush=True)

    def after_teardown_task(self, task: Task, status: TaskStatus) -> None:
        print(self.teardown_prefix, task.address, self.status_to_text(status), flush=True)
        with self._lock:
            self._status[task.address] = status
