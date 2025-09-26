from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from pathlib import Path

from loguru import logger

from kraken.core import Project, Property, Task, TaskRelationship
from kraken.core.system.task import TaskStatus

from ..settings import python_settings


class PublishTask(Task):
    """Publishes Python distributions to one or more indexes using `uv publish`."""

    description = "Upload the distributions of your Python project. [index url: %(index_upload_url)s]"
    index_upload_url: Property[str]
    index_index_url: Property[str]
    index_credentials: Property[tuple[str, str] | None] = Property.default(None)
    distributions: Property[list[Path]]
    skip_existing: Property[bool] = Property.default(False)
    interactive: Property[bool | None] = Property.default(None)
    dependencies: list[Task]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.dependencies = []

    def get_relationships(self) -> Iterable[TaskRelationship]:
        yield from (TaskRelationship(task, True, False) for task in self.dependencies)
        yield from super().get_relationships()

    def execute(self) -> TaskStatus:
        # Check for the deprecated property
        if self.interactive.get() is not None:
            logger.warning(
                "The 'interactive' property on the python.publish task is deprecated and has no effect. "
                "uv publish is non-interactive by default in this context.",
                DeprecationWarning,
            )
        credentials = self.index_credentials.get()
        command = [
            "uv",
            "publish",
            "--no-progress",  # No spinners and progress bars in stderr
            "--publish-url",
            self.index_upload_url.get(),
            *[str(x.absolute()) for x in self.distributions.get()],
        ]
        if self.skip_existing:
            command.extend(["--check-url", self.index_index_url.get()])

        env = os.environ.copy()
        if credentials:
            if "pypi.org/" in self.index_upload_url.get() and credentials[0] != "__token__":
                logger.warning(
                    "Since 2024-01-01, PyPI no longer allows publishing with username and password, "
                    " see https://blog.pypi.org/posts/2024-01-01-2fa-enforced/"
                    " and https://docs.astral.sh/uv/guides/package/#publishing-your-package"
                )
            env["UV_PUBLISH_USERNAME"] = credentials[0]
            env["UV_PUBLISH_PASSWORD"] = credentials[1]

        safe_command = command
        self.logger.info("$ %s", safe_command)

        returncode = subprocess.call(command, cwd=self.project.directory, env=env)
        return TaskStatus.from_exit_code(safe_command, returncode)


def publish(
    *,
    package_index: str,
    distributions: list[Path] | Property[list[Path]],
    skip_existing: bool = False,
    interactive: bool | None = None,
    name: str = "python.publish",
    group: str | None = "publish",
    project: Project | None = None,
    after: list[Task] | None = None,
) -> PublishTask:
    """Create a publish task for the specified registry."""

    project = project or Project.current()
    settings = python_settings(project)
    if package_index not in settings.package_indexes:
        raise ValueError(f"package index {package_index!r} is not defined")

    index = settings.package_indexes[package_index]
    task = project.task(name, PublishTask, group=group)
    task.index_upload_url = index.upload_url
    task.index_index_url = index.index_url
    task.index_credentials = index.credentials
    task.distributions = distributions
    task.skip_existing = skip_existing
    task.interactive = interactive
    task.depends_on(*(after or []))
    return task
