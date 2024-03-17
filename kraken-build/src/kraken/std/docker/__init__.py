from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from kraken.common import Supplier, import_class
from kraken.core import Project, Task
from kraken.std.docker.tasks.base_build_task import BaseBuildTask
from kraken.std.docker.tasks.manifest_tool_push_task import ManifestToolPushTask

__all__ = ["build_docker_image", "manifest_tool"]

DEFAULT_BUILD_BACKEND = "native"
BUILD_BACKENDS = {
    "buildx": f"{__name__}.tasks.buildx_build_task.BuildxBuildTask",
    "kaniko": f"{__name__}.tasks.kaniko_build_task.KanikoBuildTask",
    "native": f"{__name__}.tasks.docker_build_task.DockerBuildTask",
}


def build_docker_image(
    *,
    name: str = "buildDocker",
    backend: str = DEFAULT_BUILD_BACKEND,
    project: Project | None = None,
    dockerfile: str | Path | Supplier[Path] = "Dockerfile",
    **kwds: Any,
) -> BaseBuildTask:
    """Create a new task in the current project that builds a Docker image and eventually pushes it."""

    project = project or Project.current()
    task_class = import_class(BUILD_BACKENDS[backend], BaseBuildTask)  # type: ignore[type-abstract]
    dockerfile = cast(Supplier[Path | str], Supplier.of(dockerfile)).map(project.directory.joinpath)
    return project.do(name, task_class, dockerfile=dockerfile, **kwds)


def manifest_tool(
    *,
    name: str,
    template: str,
    platforms: Sequence[str],
    target: str,
    inputs: Sequence[Task],
    group: str | None = None,
    project: Project | None = None,
) -> ManifestToolPushTask:
    project = Project.current()
    task = project.task(name, ManifestToolPushTask, group=group)
    task.template = template
    task.target = target
    task.platforms = list(platforms)
    task.depends_on(*inputs)
    return task
