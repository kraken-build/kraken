from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from kraken.core import Project, Property, Task, TaskRelationship
from twine.commands.upload import upload as twine_upload
from twine.settings import Settings as TwineSettings

from ..settings import python_settings


class PublishTask(Task):
    """Publishes Python distributions to one or more indexes using :mod:`twine`."""

    description = "Upload the distributions of your Python project. [index url: %(index_upload_url)s]"
    index_upload_url: Property[str]
    index_credentials: Property[Optional[Tuple[str, str]]] = Property.config(default=None)
    distributions: Property[List[Path]]
    skip_existing: Property[bool] = Property.config(default=False)
    dependencies: List[Task]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.dependencies = []

    def get_relationships(self) -> Iterable[TaskRelationship]:
        yield from (TaskRelationship(task, True, False) for task in self.dependencies)
        yield from super().get_relationships()

    def execute(self) -> None:
        credentials = self.index_credentials.get()
        settings = TwineSettings(
            repository_url=self.index_upload_url.get().rstrip("/") + "/",
            username=credentials[0] if credentials else None,
            password=credentials[1] if credentials else None,
            skip_existing=self.skip_existing.get(),
            non_interactive=True,
        )
        twine_upload(settings, list(map(str, self.distributions.get())))


def publish(
    *,
    package_index: str,
    distributions: list[Path] | Property[List[Path]],
    skip_existing: bool = False,
    name: str = "python.publish",
    group: str | None = "publish",
    default: bool = False,
    project: Project | None = None,
    after: list[Task] | None = None,
) -> PublishTask:
    """Create a publish task for the specified registry."""

    project = project or Project.current()
    settings = python_settings(project)
    if package_index not in settings.package_indexes:
        raise ValueError(f"package index {package_index!r} is not defined")

    index = settings.package_indexes[package_index]
    task = project.do(
        name,
        PublishTask,
        default=default,
        group=group,
        index_upload_url=index.upload_url,
        index_credentials=index.credentials,
        distributions=distributions,
        skip_existing=skip_existing,
    )
    task.dependencies += after or []
    return task
