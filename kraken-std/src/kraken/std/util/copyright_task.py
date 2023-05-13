from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Iterable, List

from kraken.core.api import Project, Property

from kraken.std.python.tasks.base_task import EnvironmentAwareDispatchTask


class CopyrightTask(EnvironmentAwareDispatchTask):
    """A task to run the `pyaddlicense` command to ensure copyright files exist in all source files."""

    python_dependencies = ["pyaddlicense"]

    check_only: Property[bool] = Property.config(default=False)
    holder: Property[str] = Property.config(default="")
    ignore: Property[List[str]] = Property.config(default_factory=list)
    custom_license: Property[str]
    custom_license_file: Property[Path]

    def get_execute_command(self) -> List[str]:
        command = ["pyaddlicense"]

        if self.holder.get() != "":
            command += ["-o", f"'{self.holder.get()}'"]

        if self.check_only.get():
            command += ["-c"]

        if self.custom_license.is_filled():
            command += ["-l", f"'{str(self.custom_license.get())}'"]

        if self.custom_license_file.is_filled():
            command += ["-f", str(self.custom_license_file.get().absolute())]

        for custom_ignore in self.ignore.get():
            command += ["-i", custom_ignore]

        return command

    def get_description(self) -> str | None:
        if self.check_only.get():
            return "Check all source files start with a copyright comment via addlicense."
        else:
            return (
                "Check all source files start with a copyright message and edit them to include it if they do "
                "not (via addlicense)."
            )


@dataclasses.dataclass
class CopyrightTasks:
    check: CopyrightTask
    format: CopyrightTask


def check_and_format_copyright(
    holder: str, name: str = "copyright", project: Project | None = None, ignore: Iterable[str] = [], **kwargs: Any
) -> CopyrightTasks:
    """Creates two copyright tasks, one to check and another to format. The check task will be grouped under `"lint"`
    whereas the format task will be grouped under `"fmt"`."""

    project = project or Project.current()
    check_task = project.do(
        name=f"{name}.check",
        task_type=CopyrightTask,
        group="lint",
        check_only=True,
        holder=holder,
        ignore=ignore,
        **kwargs,
    )
    format_task = project.do(
        name=f"{name}.fmt",
        task_type=CopyrightTask,
        group="fmt",
        check_only=False,
        holder=holder,
        ignore=ignore,
        **kwargs,
    )
    return CopyrightTasks(check_task, format_task)
