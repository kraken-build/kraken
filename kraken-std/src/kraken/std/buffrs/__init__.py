from __future__ import annotations

import logging
from typing import Any, cast

from kraken.common import CredentialsWithHost
from kraken.core import Project

from .tasks import (
    BuffrsBumpVersionTask,
    BuffrsGenerateTask,
    BuffrsInstallTask,
    BuffrsLoginTask,
    BuffrsPublishTask,
    Language,
)

logger = logging.getLogger(__name__)

__all__ = ["buffrs_login", "buffrs_publish", "buffrs_bump_version"]

PROTO_REPO = "proto"

PYTHON_BUILD_TASK_NAME = "python.build"


def buffrs_login(
    *,
    project: Project | None = None,
    artifactory_credentials: CredentialsWithHost,
) -> BuffrsLoginTask:
    """Logs buffrs into Artifactory."""

    project = project or Project.current()
    root_project = project.context.root_project

    if "buffrsLogin" in root_project.tasks():
        return cast(BuffrsLoginTask, root_project.task("buffrsLogin"))

    task = root_project.do(
        "buffrsLogin",
        BuffrsLoginTask,
        artifactory_credentials=artifactory_credentials,
    )

    return task


def buffrs_bump_version(
    *,
    project: Project | None = None,
    version: str,
) -> BuffrsBumpVersionTask:
    """Creates a task that bumps the version in `Proto.toml`.

    :param version: The version number to bump to.
    """

    project = project or Project.current()

    task = project.do(
        "buffrsBumpVersion",
        BuffrsBumpVersionTask,
        version=version,
        group="publish",
    )

    return task


CARGO_BUILD_SUPPORT_GROUP_NAME = "cargoBuildSupport"


def buffrs_install(
    *,
    project: Project | None = None,
) -> BuffrsInstallTask:
    """Installs buffrs dependencies defined in the `Proto.toml`"""

    project = project or Project.current()

    task = project.do(
        "buffrsInstall",
        BuffrsInstallTask,
    )

    # TODO(alex.spencer) - move this over to cargoBuildSupport - how would we get the task reference as this step happens after cargo_project?
    if (
        task.project.context.root_project == project
        and CARGO_BUILD_SUPPORT_GROUP_NAME in project.context.root_project.tasks()
    ):
        logger.debug(
            "%s: %s group found in root project tasks. Adding this task to the root project's groups",
            task.name,
            CARGO_BUILD_SUPPORT_GROUP_NAME,
        )
        project.context.root_project.group(CARGO_BUILD_SUPPORT_GROUP_NAME).add(task)  # Add to the ROOT project

    return task


def buffrs_publish(
    *,
    project: Project | None = None,
    artifactory_repository: str,
) -> BuffrsPublishTask:
    """Publishes the buffrs package to the repository of the project."""

    project = project or Project.current()

    task = project.do(
        "buffrsPublish",
        BuffrsPublishTask,
        artifactory_repository=artifactory_repository,
        group="publish",
    )

    return task


def buffrs_generate(
    *,
    name: str,
    project: Project | None = None,
    language: Language,
    generated_output_dir: str,
    **kwargs: Any,
) -> BuffrsGenerateTask:
    """Generates code for installed packages with buffrs. Should only be called for python projects that have a Proto.toml file"""

    project = project or Project.current()

    task = project.do(
        "buffrsGenerate",
        BuffrsGenerateTask,
        language=language,
        generated_output_dir=generated_output_dir,
    )

    # TODO(alex.spencer) - I'm not sure this is the right place to put this - but unsure how to separate it out
    # logger.warning(f":{project.name}:{PYTHON_BUILD_TASK_NAME}?")
    task.required_by(f":{project.name}:{PYTHON_BUILD_TASK_NAME}?")

    return task
