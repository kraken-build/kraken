from __future__ import annotations

import dataclasses
from collections.abc import MutableMapping, Sequence
from pathlib import Path

from kraken.core import Project, Property
from kraken.core.system.task import TaskStatus
from kraken.std.python.tasks.base_task import EnvironmentAwareDispatchTask


class CopyrightTask(EnvironmentAwareDispatchTask):
    """A task to run the `pyaddlicense` command to ensure copyright files exist in all source files."""

    python_dependencies = ["pyaddlicense"]

    check_only: Property[bool] = Property.default(False)
    holder: Property[str] = Property.default("")
    ignore: Property[Sequence[str]] = Property.default_factory(list)
    custom_license: Property[str]
    custom_license_file: Property[Path]

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str] | TaskStatus:
        command = ["pyaddlicense"]

        if self.holder.get() != "":
            command += ["-o", f"{self.holder.get()}"]

        if self.check_only.get():
            command += ["-c"]

        if self.custom_license.is_filled():
            command += ["-l", f"{str(self.custom_license.get())}"]

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
    holder: str,
    name: str = "copyright",
    project: Project | None = None,
    ignore: Sequence[str] = (),
    custom_license: str | None = None,
    custom_license_file: Path | None = None,
) -> CopyrightTasks:
    """Creates two copyright tasks, one to check and another to format. The check task will be grouped under `"lint"`
    whereas the format task will be grouped under `"fmt"`."""

    project = project or Project.current()
    check_task = project.task(f"{name}.check", CopyrightTask, group="lint")
    check_task.check_only = True
    check_task.holder = holder
    check_task.ignore = ignore
    check_task.custom_license = custom_license
    check_task.custom_license_file = custom_license_file

    format_task = project.task(f"{name}.fmt", CopyrightTask, group="fmt")
    format_task.check_only = False
    format_task.holder = holder
    format_task.ignore = ignore
    format_task.custom_license = custom_license
    format_task.custom_license_file = custom_license_file

    return CopyrightTasks(check_task, format_task)
