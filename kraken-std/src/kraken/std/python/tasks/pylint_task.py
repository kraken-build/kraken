from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class PylintTask(EnvironmentAwareDispatchTask):
    description = "Lint Python source files with Pylint"
    python_dependencies = ["pylint"]

    config_file: Property[Path]
    additional_args: Property[Sequence[str]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = ["pylint", str(self.settings.source_directory)] + self.settings.get_tests_directory_as_args()
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        if self.config_file.is_filled():
            command += ["--rcfile", str(self.config_file.get())]
        command += self.additional_args.get()
        return command


def pylint(
    *,
    name: str = "python.pylint",
    project: Project | None = None,
    config_file: Path | Supplier[Path] | None = None,
    additional_args: Sequence[str] | Property[Sequence[str]] = (),
) -> PylintTask:
    project = project or Project.current()
    task = project.task(name, PylintTask, group="lint")
    task.config_file = config_file
    task.additional_args = additional_args
    return task
