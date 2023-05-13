from __future__ import annotations

from pathlib import Path
from typing import Any, List

from kraken.core.api import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class Flake8Task(EnvironmentAwareDispatchTask):
    description = "Lint Python source files with Flake8."
    python_dependencies = ["flake8"]

    config_file: Property[Path]
    additional_args: Property[List[str]] = Property.config(default_factory=list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = ["flake8", str(self.settings.source_directory)] + self.settings.get_tests_directory_as_args()
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get().absolute())]
        command += self.additional_args.get()
        return command


def flake8(*, name: str = "python.flake8", project: Project | None = None, **kwargs: Any) -> Flake8Task:
    project = project or Project.current()
    return project.do(name, Flake8Task, group="lint", **kwargs)
