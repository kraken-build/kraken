from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, List

from kraken.core.api import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class PyclnTask(EnvironmentAwareDispatchTask):
    """A task to run the `pycln` formatter to either check for necessary changes or apply changes."""

    python_dependencies = ["pycln"]

    check_only: Property[bool] = Property.config(default=False)
    config_file: Property[Path]
    additional_args: Property[List[str]] = Property.config(default_factory=list)
    additional_files: Property[List[Path]] = Property.config(default_factory=list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = ["pycln", str(self.settings.source_directory)]
        command += self.settings.get_tests_directory_as_args()
        command += [str(p) for p in self.additional_files.get()]
        if self.check_only.get():
            command += ["--check", "--diff"]
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get().absolute())]
        command += self.additional_args.get()
        return command

    def get_description(self) -> str:
        if self.check_only.get():
            return "Check Python imports with Pycln."
        else:
            return "Remove unused Python imports with Pycln."


@dataclasses.dataclass
class PyclnTasks:
    check: PyclnTask
    format: PyclnTask


def pycln(*, name: str = "python.pycln", project: Project | None = None, **kwargs: Any) -> PyclnTasks:
    """Creates two pycln tasks, one to check and another to format. The check task will be grouped under `"lint"`
    whereas the format task will be grouped under `"fmt"`."""

    project = project or Project.current()
    check_task = project.do(f"{name}.check", PyclnTask, group="lint", **kwargs, check_only=True)
    format_task = project.do(name, PyclnTask, group="fmt", default=False, **kwargs)
    return PyclnTasks(check_task, format_task)
