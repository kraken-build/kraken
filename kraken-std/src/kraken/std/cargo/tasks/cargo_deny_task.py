import subprocess
from collections.abc import Sequence
from pathlib import Path

from kraken.core import Property, Task, TaskStatus


class CargoDenyTask(Task):
    description = "Executes cargo deny to verify dependencies."
    checks: Property[Sequence[str]] = Property.default_factory(list)
    config_file: Property[Path]
    error_message: Property[str | None] = Property.default(None)

    def execute(self) -> TaskStatus:
        command = ["cargo", "deny", "check"]

        if self.config_file.is_filled():
            command.extend(["--config", str(self.config_file.get().absolute())])

        command.extend(self.checks.get())

        result = subprocess.run(command, cwd=self.project.directory)
        if result.returncode == 0:
            return TaskStatus.succeeded()

        return self.error_message.map(
            lambda message: TaskStatus.failed(message)
            if message is not None
            else TaskStatus.from_exit_code(command, result.returncode)
        ).get()
