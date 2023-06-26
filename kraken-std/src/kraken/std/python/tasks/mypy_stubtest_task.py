from __future__ import annotations

from pathlib import Path

from kraken.core import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class MypyStubtestTask(EnvironmentAwareDispatchTask):
    description = "Static validation for Python type stubs using Mypy."
    python_dependencies = ["mypy"]

    package: Property[str]
    ignore_missing_stubs: Property[bool] = Property.default(False)
    ignore_positional_only: Property[bool] = Property.default(False)
    allowlist: Property[Path]
    mypy_config_file: Property[Path]

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = ["python", "-m", "mypy.stubtest", self.package.get()]
        if self.ignore_missing_stubs.get():
            command.append("--ignore-missing-stub")
        if self.ignore_positional_only.get():
            command.append("--ignore-positional-only")
        if self.allowlist.is_filled():
            command.extend(("--allowlist", str(self.allowlist.get().absolute())))
        if self.mypy_config_file.is_filled():
            command.extend(("--mypy-config-file", str(self.mypy_config_file.get().absolute())))
        return command


def mypy_stubtest(
    *,
    name: str = "python.mypy.stubtest",
    project: Project | None = None,
    package: str,
    ignore_missing_stubs: bool = False,
    ignore_positional_only: bool = False,
    allowlist: Path | None = None,
    mypy_config_file: Path | None = None,
) -> MypyStubtestTask:
    project = project or Project.current()
    task = project.task(name, MypyStubtestTask, group="lint")
    task.package = package
    task.ignore_missing_stubs = ignore_missing_stubs
    task.ignore_positional_only = ignore_positional_only
    task.allowlist = allowlist
    task.mypy_config_file = mypy_config_file
    return task
