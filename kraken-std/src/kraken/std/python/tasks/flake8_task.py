from __future__ import annotations

from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class Flake8Task(EnvironmentAwareDispatchTask):
    """
    Lint Python source files with Flake8.
    """

    description = "Lint Python source files with Flake8."
    python_dependencies = ["flake8"]

    config_file: Property[Path]
    additional_args: Property[list[str]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = ["flake8", str(self.settings.source_directory)] + self.settings.get_tests_directory_as_args()
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get().absolute())]
        command += self.additional_args.get()
        return command


def flake8(
    *, name: str = "python.flake8", project: Project | None = None, config_file: Path | Supplier[Path] | None = None
) -> Flake8Task:
    project = project or Project.current()
    task = project.task(name, Flake8Task, group="lint")
    if config_file is not None:
        task.config_file = config_file
    return task
