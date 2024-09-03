from collections.abc import Callable
import hashlib
import os
from pathlib import Path
import sys
from typing import NewType

from attr import dataclass
from loguru import logger
from kraken.core.system.executor.default import DefaultTaskExecutor
from concurrent.futures import Future, ProcessPoolExecutor

from kraken.core.system.task import Task, TaskStatus

TaskId = NewType("TaskId", str)


@dataclass
class _Execution:
    task: Task
    future: Future[TaskStatus]
    log_file: Path
    done: Callable[[TaskStatus], None]


class ParallelTaskExecutor(DefaultTaskExecutor):
    def __init__(self, build_logs_dir: Path, max_workers: int | None = None):
        self._build_logs_dir = build_logs_dir
        self._pool = ProcessPoolExecutor(max_workers=max_workers)
        self._executions: dict[TaskId, _Execution] = {}
        self._started = False

    def _call_redirect_output(
        self, task_id: TaskId, log_file: Path, func: Callable[[], TaskStatus | None]
    ) -> TaskStatus:
        logger.debug("Redirecting output of task '{}' to '{}' (pid: {})", task_id, log_file, os.getpid())
        with log_file.open("wb") as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())
            return self._call(func)

    def execute_task(self, task: Task, done: Callable[[TaskStatus], None]) -> None:
        if not self._started:
            self._build_logs_dir.mkdir(parents=True, exist_ok=True)
            self._started = True

        task_id = TaskId(str(task.address))
        log_file = self._build_logs_dir / f"{hashlib.md5(task_id.encode()).hexdigest()}.log"
        future = self._pool.submit(self._call_redirect_output, task_id, log_file, task.execute)

        # TODO: We likely need to send back the task state as its output properties may have changed.

        def callback(f: Future[TaskStatus]) -> None:
            try:
                status = f.result()
            except BaseException as exc:
                status = TaskStatus.failed(str(exc))
            logger.debug("Task '{}' completed with status {}", task_id, status)
            done(status)

        future.add_done_callback(callback)

    def teardown_task(self, task: Task, done: Callable[[TaskStatus], None]) -> None:
        # TODO: This will likely fail for tasks that commit state changes in execute() and rely on that stat
        #       in teardown().
        return super().teardown_task(task, done)
