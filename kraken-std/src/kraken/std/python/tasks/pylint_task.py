from __future__ import annotations

from pathlib import Path
from typing import Any, List

from kraken.core.api import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class PylintTask(EnvironmentAwareDispatchTask):
    description = "Lint Python source files with Pylint"
    python_dependencies = ["pylint"]

    config_file: Property[Path]
    additional_args: Property[List[str]] = Property.config(default_factory=list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = ["pylint", str(self.settings.source_directory)] + self.settings.get_tests_directory_as_args()
        if self.config_file.is_filled():
            command += ["--rcfile", str(self.config_file.get())]
        command += self.additional_args.get()
        return command


def pylint(*, name: str = "python.pylint", project: Project | None = None, **kwargs: Any) -> PylintTask:
    project = project or Project.current()
    return project.do(name, PylintTask, group="lint", **kwargs)
