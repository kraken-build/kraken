from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from kraken.common import import_class
from kraken.core import Project, Task
from kraken.core.system.property import Property
from kraken.core.system.task import GroupTask
from kraken.std.docker.tasks.base_build_task import BaseBuildTask
from kraken.std.docker.tasks.manifest_tool_push_task import ManifestToolPushTask

__all__ = ["build_docker_image", "manifest_tool", "sidecar_container"]

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
    default: bool = False,
    group: str | GroupTask | None = None,
    description: str | None = None,
    **kwds: Any,
) -> BaseBuildTask:
    """Create a new task in the current project that builds a Docker image and eventually pushes it."""

    project = project or Project.current()
    task_class = import_class(BUILD_BACKENDS[backend], BaseBuildTask)  # type: ignore[type-abstract]
    task = project.task(name, task_class, default=default, group=group, description=description)

    # Assign properties from the kwargs.
    invalid_keys = set()
    for key, value in kwds.items():
        prop = getattr(task, key, None)
        if isinstance(prop, Property):
            if value is not None:
                prop.set(value)
        else:
            invalid_keys.add(key)
    if invalid_keys:
        task.logger.warning(
            "properties %s cannot be set because they don't exist (task %s)", invalid_keys, task.address
        )

    return task


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
