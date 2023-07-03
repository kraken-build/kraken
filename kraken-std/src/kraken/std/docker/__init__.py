from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from kraken.common import import_class
from kraken.core import Project, Task

from kraken.std.docker.tasks.base_build_task import BaseBuildTask
from kraken.std.docker.tasks.manifest_tool_push_task import ManifestToolPushTask
from kraken.std.docker.tasks.run_container_task import RunContainerTask, StopContainerTask, WaitForProcessTask

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


@dataclass(frozen=True)
class SidecarContainerRecord:
    name: str
    image: str
    ports: Sequence[str]
    env: Mapping[str, str]
    args: Sequence[str]
    workdir: str | None
    entrypoint: str | None
    cwd: Path | None
    detach: bool

    run_task: RunContainerTask
    stop_task: StopContainerTask | None
    wait_task: WaitForProcessTask | None


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
    detach: bool = True,
    project: Project | None = None,
) -> RunContainerTask:
    """
    Define a Docker container to run in the background. This is useful to define containers that should run in the
    background and be available for other tasks to connect to. For example, a database container that should be
    available for a test suite to connect to.

    If *detach* is enabled, the container will keep running in the background even when Kraken exits. It will be
    restarted if its configuration is updated (i.e. the parameters to this function).
    """

    project = project or Project.current()

    container_name = "kraken.sidecar-container." + (
        str(project.address).replace(":", ".").strip(".") + "." + name
    ).strip(".")

    task = project.task(f"{name}.start", RunContainerTask)
    task.container_name = container_name
    task.image = image
    task.ports = ports
    task.env = env
    task.args = args
    task.workdir = workdir
    task.entrypoint = entrypoint
    task.cwd = cwd

    if detach:
        wait = None
        stop = project.task(f"{name}.stop", StopContainerTask)
        stop.container_name = container_name
    else:
        wait = project.task(name, WaitForProcessTask)
        wait.pid = task._pid
        wait.depends_on(task)
        stop = None

    metadata = SidecarContainerRecord(
        name=name,
        image=image,
        ports=ports,
        env=env,
        args=args,
        workdir=workdir,
        entrypoint=entrypoint,
        cwd=cwd,
        detach=detach,
        run_task=task,
        stop_task=stop,
        wait_task=wait,
    )
    project.metadata.append(metadata)

    return task
