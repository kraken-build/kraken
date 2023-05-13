import subprocess
from pathlib import Path
from typing import Sequence

from kraken.core import Task, TaskStatus
from kraken.core.api import Property


class CargoDenyTask(Task):
    description = "Executes cargo deny to verify dependencies."
    checks: Property[Sequence[str]] = Property.default_factory(list)
    config_file: Property[Path]

    def execute(self) -> TaskStatus:
        command = ["cargo", "deny", "check"]

        if self.config_file.is_filled():
            command.extend(["--config", str(self.config_file.get().absolute())])

        command.extend(self.checks.get())

        result = subprocess.run(command, cwd=self.project.directory)
        return TaskStatus.from_exit_code(command, result.returncode)
