from __future__ import annotations

import logging
import platform as _platform
from pathlib import Path
from typing import cast

from kraken.common.supplier import Supplier
from kraken.core import Project

from .tasks import BuffrsInstallTask, BuffrsLoginTask, BuffrsPublishTask
from kraken.std.util import fetch_tarball

logger = logging.getLogger(__name__)

__all__ = ["buffrs_login", "buffrs_publish"]

PYTHON_BUILD_TASK_NAME = "python.build"


def buffrs_login(
    *,
    project: Project | None = None,
    registry: str,
    token: str,
    buffrs_bin: Supplier[str] | None = None,
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
        task.buffrs_bin = buffrs_bin or buffrs_fetch_binary().map(str)

    return task


def buffrs_install(*, project: Project | None = None,
    buffrs_bin: Supplier[str] | None = None,) -> BuffrsInstallTask:
    """Installs buffrs dependencies defined in the `Proto.toml`"""

    project = project or Project.current()
    task = project.task("buffrsInstall", BuffrsInstallTask)
    task.buffrs_bin = buffrs_bin or buffrs_fetch_binary().map(str)

    return task


def buffrs_publish(
    *,
    project: Project | None = None,
    registry: str,
    repository: str,
    version: str | None = None,
    buffrs_bin: Supplier[str] | None = None,
) -> BuffrsPublishTask:
    """Publishes the buffrs package to the repository of the project."""

    project = project or Project.current()

    task = project.task("buffrsPublish", BuffrsPublishTask)
    task.registry = registry
    task.repository = repository
    task.version = version
    task.buffrs_bin = buffrs_bin or buffrs_fetch_binary().map(str)
    return task


def buffrs_fetch_binary(
    version: str = "0.8.0",
    target_triplet: str | None = None,
) -> Supplier[Path]:
    """Fetches the path to the Buffrs binary and returns a supplier for the Path to it.

    The binary will be fetched from the [GitHub releases](https://github.com/helsing-ai/buffrs/releases).
    """

    target_triplet = target_triplet or get_buffrs_triplet()
    suffix = ".zip" if "-windows" in target_triplet else ".tar.gz"
    binary = "buffrs.exe" if "-windows" in target_triplet else "buffrs"
    name = f"buffrs-v{version}-{target_triplet}"
    url = f"https://github.com/helsing-ai/buffrs/releases/download/v{version}/{name}{suffix}"

    return fetch_tarball(name="buffrs", url=url).out.map(lambda p: p.absolute() / name / binary)


def get_buffrs_triplet() -> str:
    """ Returns the Buffrs target triplet for the current platform."""

    match (_platform.machine(), _platform.system()):
        case ("x86_64", "Linux"):
            return "x86_64-unknown-linux-gnu"
        case ("x86_64", "Darwin"):
            return "x86_64-apple-darwin"
        case ("x86_64", "Windows"):
            return "x86_64-pc-windows-msvc"
        case ("aarch64", "Linux"):
            return "arm-unknown-linux-gnueabihf"
        case ("aarch64", "Darwin"):
            return "aarch64-apple-darwin"
        case ("aarch64", "Windows"):
            return "i686-pc-windows-msvc"
        case _:
            raise NotImplementedError(f"Platform {_platform.machine()} is not supported by Buffrs.")
