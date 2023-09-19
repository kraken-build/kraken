from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class BlackTask(EnvironmentAwareDispatchTask):
    """A task to run the `black` formatter to either check for necessary changes or apply changes."""

    python_dependencies = ["black"]

    check_only: Property[bool] = Property.default(False)
    config_file: Property[Path]
    additional_args: Property[Sequence[str]] = Property.default_factory(list)
    additional_files: Property[Sequence[Path]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = ["black", str(self.settings.source_directory)]
        command += self.settings.get_tests_directory_as_args()
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
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


def black(
    *,
    name: str = "python.black",
    project: Project | None = None,
    config_file: Path | Supplier[Path] | None = None,
    additional_args: Sequence[str] | Supplier[Sequence[str]] = (),
    additional_files: Sequence[Path] | Supplier[Sequence[Path]] = (),
) -> BlackTasks:
    """Creates two black tasks, one to check and another to format. The check task will be grouped under `"lint"`
    whereas the format task will be grouped under `"fmt"`."""

    project = project or Project.current()
    check_task = project.task(f"{name}.check", BlackTask, group="lint")
    check_task.check_only = True
    check_task.config_file = config_file
    check_task.additional_args = additional_args
    check_task.additional_files = additional_files

    format_task = project.task(name, BlackTask, group="fmt")
    format_task.check_only = False
    format_task.config_file = config_file
    format_task.additional_args = additional_args
    format_task.additional_files = additional_files

    return BlackTasks(check_task, format_task)
