from __future__ import annotations

from pathlib import Path
from typing import Optional

from kraken.core.api import Project, Property, Task, TaskStatus
from nr.stream import Supplier

from ..buildsystem import PythonBuildSystem
from ..pyproject import Pyproject
from ..settings import PythonSettings, python_settings


class UpdateLockfileTask(Task):
    settings: Property[PythonSettings]
    build_system: Property[Optional[PythonBuildSystem]]
    pyproject_toml: Property[Path]

    def get_description(self) -> str | None:
        build_system = self.build_system.get()
        return (
            f"Update dependencies in your Python project. [build system: "
            f"{build_system.name if build_system else None}]"
        )

    def execute(self) -> TaskStatus:
        build_system = self.build_system.get()
        if not build_system:
            return TaskStatus.failed("no build system configured")
        settings = self.settings.get()
        pyproject = Pyproject.read(self.pyproject_toml.get())
        return build_system.update_lockfile(settings, pyproject)


def update_lockfile_task(
    *,
    name: str = "python.update",
    group: str | None = "update",
    as_version: str | None = None,
    project: Project | None = None,
) -> UpdateLockfileTask:
    """Creates an update task for the given project.

    The update task relies on the build system configured in the Python project settings."""

    project = project or Project.current()
    task = project.do(
        name,
        UpdateLockfileTask,
        group=group,
        settings=python_settings(project),
        build_system=Supplier.of_callable(lambda: python_settings(project).build_system),
        pyproject_toml=project.directory / "pyproject.toml",
    )
    return task
