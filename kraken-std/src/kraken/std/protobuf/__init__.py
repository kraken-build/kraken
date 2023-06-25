from __future__ import annotations

import subprocess as sp

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


def buf_format(*, name: str = "buf.format", project: Project | None = None) -> BufFormatTask:
    project = project or Project.current()
    return project.task(name, BufFormatTask, group="fmt")


def buf_lint(*, name: str = "buf.lint", project: Project | None = None) -> BufLintTask:
    project = project or Project.current()
    return project.task(name, BufLintTask, group="lint")
