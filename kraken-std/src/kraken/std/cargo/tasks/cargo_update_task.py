from __future__ import annotations

import subprocess as sp

from kraken.core import Task, TaskStatus


class CargoUpdateTask(Task):
    def execute(self) -> TaskStatus:
        command = ["cargo", "update"]
        return TaskStatus.from_exit_code(command, sp.call(command, cwd=self.project.directory))

    def get_description(self) -> str | None:
        return "Run `cargo update`."
