from __future__ import annotations

import logging
from typing import cast

from kraken.core import Project

from .tasks import BuffrsInstallTask, BuffrsLoginTask, BuffrsPublishTask

logger = logging.getLogger(__name__)

__all__ = ["buffrs_login", "buffrs_publish"]

PYTHON_BUILD_TASK_NAME = "python.build"


def buffrs_login(
    *,
    project: Project | None = None,
    registry: str,
    token: str,
) -> BuffrsLoginTask:
    """Create a task to log into an Artifactory registry with Buffrs. The task is created in the root project
    regardless from where it is called. Note that currently we only support a single registry to push to, because
    we always use `buffrsLogin` as the task name."""

    project = project or Project.current()
    root_project = project.context.root_project

    if "buffrsLogin" in root_project.tasks():
        task = cast(BuffrsLoginTask, root_project.task("buffrsLogin"))
        if task.registry.get() != registry or task.token.get() != token:
            raise RuntimeError("multiple buffrs_login() calls with different registry/token not currently supported")
    else:
        task = root_project.task("buffrsLogin", BuffrsLoginTask)
        task.registry = registry
        task.token = token

    return task


def buffrs_install(*, project: Project | None = None) -> BuffrsInstallTask:
    """Installs buffrs dependencies defined in the `Proto.toml`"""

    project = project or Project.current()
    return project.task("buffrsInstall", BuffrsInstallTask)


def buffrs_publish(
    *,
    project: Project | None = None,
    registry: str,
    repository: str,
    version: str | None = None,
) -> BuffrsPublishTask:
    """Publishes the buffrs package to the repository of the project."""

    project = project or Project.current()

    task = project.task("buffrsPublish", BuffrsPublishTask)
    task.registry = registry
    task.repository = repository
    task.version = version
    return task
