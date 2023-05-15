from __future__ import annotations

import logging
import os
from typing import Optional, Union, cast

from kraken.common import Supplier
from kraken.common.pyenv import get_current_venv
from kraken.core import Project, Property, Task, TaskStatus

from ..buildsystem import PythonBuildSystem
from ..settings import python_settings

logger = logging.getLogger(__name__)


class InstallTask(Task):
    build_system: Property[Optional[PythonBuildSystem]]
    always_use_managed_env: Property[bool]

    # Task

    def get_description(self) -> str | None:
        build_system = self.build_system.get()
        return (
            f"Ensure that a managed virtual environment exists. [build system: "
            f"{build_system.name if build_system else None}]"
        )

    def prepare(self) -> TaskStatus | None:
        venv = get_current_venv(os.environ)
        if not self.always_use_managed_env.get() and venv:
            return TaskStatus.skipped("using current virtual env (%s)" % venv.path)
        build_system = self.build_system.get()
        if not build_system:
            return TaskStatus.skipped("no Python build system configured")
        if not build_system.supports_managed_environments():
            return TaskStatus.skipped(
                "current build system does not supported managed environment (%s)" % type(build_system).__name__
            )
        managed_environment = build_system.get_managed_environment()
        if managed_environment.exists() and not managed_environment.always_install():
            if self.selected:
                return TaskStatus.pending("explicitly selected to run")
            return TaskStatus.skipped("managed environment exists (%s)" % managed_environment.get_path())

        return TaskStatus.pending()

    def execute(self) -> TaskStatus:
        build_system = self.build_system.get()
        if not build_system:
            logger.error("no build system configured")
            return TaskStatus.failed("no build system configured")
        managed_environment = build_system.get_managed_environment()
        managed_environment.install(python_settings(self.project))
        return TaskStatus.succeeded()


def install(*, name: str = "python.install", project: Project | None = None) -> InstallTask:
    """Get or create the `python.install` task for the given project.

    The install task relies on the build system configured in the Python project settings."""

    project = project or Project.current()
    task = cast(Union[InstallTask, None], project.tasks().get(name))
    if task is None:
        task = project.do(name, InstallTask, default=False)
        task.build_system.set(Supplier.of_callable(lambda: python_settings(project).build_system))
        task.always_use_managed_env.set(Supplier.of_callable(lambda: python_settings(project).always_use_managed_env))

    return task
