from __future__ import annotations

import subprocess as sp
from typing import Any

from kraken.core import Project, Task, TaskStatus


class BufFormatTask(Task):
    description = "Format Protobuf files with buf."

    def execute(self) -> TaskStatus | None:
        command = ["buf", "format", "-w"]
        result = sp.call(command)

        return TaskStatus.from_exit_code(command, result)


class BufLintTask(Task):
    description = "Lint Protobuf files with buf."

    def execute(self) -> TaskStatus | None:
        command = ["buf", "lint"]
        result = sp.call(command, cwd=self.project.directory / "proto")

        return TaskStatus.from_exit_code(command, result)


def buf_format(*, name: str = "buf.format", project: Project | None = None, **kwargs: Any) -> BufFormatTask:
    project = project or Project.current()
    return project.do(name, BufFormatTask, group="fmt", **kwargs)


def buf_lint(*, name: str = "buf.lint", project: Project | None = None, **kwargs: Any) -> BufLintTask:
    project = project or Project.current()
    return project.do(name, BufLintTask, group="lint", **kwargs)
