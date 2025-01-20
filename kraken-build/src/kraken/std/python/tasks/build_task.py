from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property, Task, TaskStatus

from ..buildsystem import PythonBuildSystem
from ..settings import python_settings

logger = logging.getLogger(__name__)


class BuildTask(Task):
    build_system: Property[PythonBuildSystem | None]
    output_directory: Property[Path]
    as_version: Property[str | None] = Property.default(None)
    output_files: Property[list[Path]] = Property.output()

    # Task

    def get_description(self) -> str | None:
        build_system = self.build_system.get()
        return (
            f"Build distributions for your Python project. [build system: "
            f"{build_system.name if build_system else None}]"
        )

    def execute(self) -> TaskStatus:
        build_system = self.build_system.get()
        if not build_system:
            return TaskStatus.failed("no build system configured")

        output_directory = self.output_directory.get_or(self.project.build_directory / "python-dist")
        output_directory.mkdir(exist_ok=True, parents=True)

        with contextlib.ExitStack() as stack:
            if as_version := self.as_version.get():
                stack.enter_context(build_system.bump_version(as_version))
            self.output_files.set(build_system.build_v2(python_settings(self.project), output_directory))

        return TaskStatus.succeeded()


def build(
    *,
    name: str = "python.build",
    group: str | None = "build",
    as_version: str | None = None,
    project: Project | None = None,
) -> BuildTask:
    """Creates a build task for the given project.

    The build task relies on the build system configured in the Python project settings."""

    project = project or Project.current()
    task = project.task(name, BuildTask, group=group)
    task.build_system = Supplier.of_callable(lambda: python_settings(project).build_system)
    task.as_version = as_version
    return task
