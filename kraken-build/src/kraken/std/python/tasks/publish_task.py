from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

from kraken.core import Project, Property, Task, TaskRelationship
from kraken.core.system.task import TaskStatus
from kraken.std.python.tasks.pex_build_task import pex_build

from ..settings import python_settings


class PublishTask(Task):
    """Publishes Python distributions to one or more indexes using :mod:`twine`."""

    description = "Upload the distributions of your Python project. [index url: %(index_upload_url)s]"
    twine_bin: Property[Path]
    index_upload_url: Property[str]
    index_credentials: Property[tuple[str, str] | None] = Property.default(None)
    distributions: Property[list[Path]]
    skip_existing: Property[bool] = Property.default(False)
    interactive: Property[bool] = Property.default(True)
    dependencies: list[Task]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.dependencies = []

    def get_relationships(self) -> Iterable[TaskRelationship]:
        yield from (TaskRelationship(task, True, False) for task in self.dependencies)
        yield from super().get_relationships()

    def execute(self) -> TaskStatus:
        credentials = self.index_credentials.get()
        repository_url = self.index_upload_url.get().rstrip("/") + "/"
        command = [
            str(self.twine_bin.get()),
            "upload",
            "--repository-url",
            repository_url,
            "--verbose",
            *[str(x.absolute()) for x in self.distributions.get()],
        ]
        if credentials:
            command += [
                "--username",
                credentials[0],
                "--password",
                credentials[1],
            ]
        if not self.interactive.get():
            command.append("--non-interactive")
        if self.skip_existing.get():
            command.append("--skip-existing")

        safe_command = [x.replace(credentials[1], "MASKED") for x in command] if credentials else command
        self.logger.info("$ %s", safe_command)

        returncode = subprocess.call(command, cwd=self.project.directory)
        return TaskStatus.from_exit_code(safe_command, returncode)


def publish(
    *,
    package_index: str,
    distributions: list[Path] | Property[list[Path]],
    skip_existing: bool = False,
    interactive: bool = True,
    name: str = "python.publish",
    group: str | None = "publish",
    project: Project | None = None,
    after: list[Task] | None = None,
    twine_version: str = ">=4.0.2,<5.0.0",
) -> PublishTask:
    """Create a publish task for the specified registry."""

    project = project or Project.current()
    settings = python_settings(project)
    if package_index not in settings.package_indexes:
        raise ValueError(f"package index {package_index!r} is not defined")

    twine_bin = pex_build(
        "twine", requirements=[f"twine{twine_version}"], console_script="twine", project=project
    ).output_file

    index = settings.package_indexes[package_index]
    task = project.task(name, PublishTask, group=group)
    task.twine_bin = twine_bin
    task.index_upload_url = index.upload_url
    task.index_credentials = index.credentials
    task.distributions = distributions
    task.skip_existing = skip_existing
    task.interactive = interactive
    task.depends_on(*(after or []))
    return task
