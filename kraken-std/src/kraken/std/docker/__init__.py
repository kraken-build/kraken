from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from kraken.common import import_class
from kraken.core import Project, Task

from kraken.std.docker.tasks.base_build_task import BaseBuildTask
from kraken.std.docker.tasks.manifest_tool_push_task import ManifestToolPushTask
from kraken.std.docker.tasks.run_container_task import RunContainerTask, WaitForProcessTask

__all__ = ["build_docker_image", "manifest_tool", "sidecar_container"]

DEFAULT_BUILD_BACKEND = "native"
BUILD_BACKENDS = {
    "buildx": f"{__name__}.buildx.BuildxBuildTask",
    "kaniko": f"{__name__}.kaniko.KanikoBuildTask",
    "native": f"{__name__}.native.NativeBuildTask",
}


def build_docker_image(
    *,
    name: str = "buildDocker",
    backend: str = DEFAULT_BUILD_BACKEND,
    project: Project | None = None,
    **kwds: Any,
) -> BaseBuildTask:
    """Create a new task in the current project that builds a Docker image and eventually pushes it."""

    task_class = import_class(BUILD_BACKENDS[backend], BaseBuildTask)  # type: ignore[type-abstract]
    return (project or Project.current()).do(name, task_class, **kwds)


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


def sidecar_container(
    *,
    name: str,
    image: str,
    ports: Sequence[str] = (),
    env: dict[str, str] = {},
    args: Sequence[str] = (),
    workdir: str | None = None,
    entrypoint: str | None = None,
    cwd: Path | None = None,
    project: Project | None = None,
) -> RunContainerTask:
    project = project or Project.current()
    task = project.task(f"{name}.start", RunContainerTask)
    task.container_name = name
    task.image = image
    task.ports = ports
    task.env = env
    task.args = args
    task.workdir = workdir
    task.entrypoint = entrypoint
    task.cwd = cwd

    wait = project.task(name, WaitForProcessTask)
    wait.pid = task._pid
    wait.depends_on(task)

    return task
