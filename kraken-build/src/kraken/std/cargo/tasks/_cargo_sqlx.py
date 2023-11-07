from __future__ import annotations

import os
import subprocess as sp
from pathlib import Path

from kraken.core import Property, Task, TaskStatus


class CargoBaseSqlxTask(Task):
    base_directory: Property[Path]
    database_url: Property[str]

    def _execute_command(self, arguments: list[str]) -> TaskStatus:
        command = ["cargo", "sqlx", *arguments]
        if self.database_url.is_filled():
            command.extend(["--database-url", self.database_url.get()])

        base_directory = self.base_directory.get() if self.base_directory.is_filled() else self.project.directory

        result = sp.call(command, cwd=base_directory, env={**os.environ})

        return TaskStatus.from_exit_code(command, result)
