from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import List

from kraken.core import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class BlackTask(EnvironmentAwareDispatchTask):
    """A task to run the `black` formatter to either check for necessary changes or apply changes."""

    python_dependencies = ["black"]

    check_only: Property[bool] = Property.config(default=False)
    config_file: Property[Path]
    additional_args: Property[List[str]] = Property.config(default_factory=list)
    additional_files: Property[List[Path]] = Property.config(default_factory=list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = ["black", str(self.settings.source_directory)]
        command += self.settings.get_tests_directory_as_args()
        command += [str(p) for p in self.additional_files.get()]
        if self.check_only.get():
            command += ["--check", "--diff"]
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get().absolute())]
        command += self.additional_args.get()
        return command

    # Task

    def get_description(self) -> str | None:
        if self.check_only.get():
            return "Check Python source files formatting with Black."
        else:
            return "Format Python source files with Black."


@dataclasses.dataclass
class BlackTasks:
    check: BlackTask
    format: BlackTask


def black(*, name: str = "python.black", project: Project | None = None) -> BlackTasks:
    """Creates two black tasks, one to check and another to format. The check task will be grouped under `"lint"`
    whereas the format task will be grouped under `"fmt"`."""

    project = project or Project.current()
    check_task = project.task(f"{name}.check", BlackTask, group="lint")
    check_task.check_only = True
    format_task = project.task(name, BlackTask, group="fmt")
    return BlackTasks(check_task, format_task)
