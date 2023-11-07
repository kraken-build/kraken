from __future__ import annotations

import logging
from typing import cast

from kraken.common import CredentialsWithHost
from kraken.core import Project

from .tasks import BuffrsGenerateTask, BuffrsInstallTask, BuffrsLoginTask, BuffrsPublishTask, Language

logger = logging.getLogger(__name__)

__all__ = ["buffrs_login", "buffrs_publish", "buffrs_generate"]

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

    return task


def buffrs_publish(
    *,
    project: Project | None = None,
    artifactory_repository: str,
    version: str,
) -> BuffrsPublishTask:
    """Publishes the buffrs package to the repository of the project."""

    project = project or Project.current()

    task = project.do(
        "buffrsPublish",
        BuffrsPublishTask,
        artifactory_repository=artifactory_repository,
        group="publish",
        version=version,
    )

    return task


def buffrs_generate(
    *,
    project: Project | None = None,
    language: Language,
    generated_output_dir: str,
) -> BuffrsGenerateTask:
    """Generates code for installed packages with buffrs.
    Should only be called for python projects that have a Proto.toml file"""

    project = project or Project.current()

    task = project.do(
        "buffrsGenerate",
        BuffrsGenerateTask,
        language=language,
        generated_output_dir=generated_output_dir,
        group="gen",
    )

    return task
