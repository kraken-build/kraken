from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kraken.core import Project, VoidTask


@dataclass
class Resource:
    """A resource represents a file or directory on the file system."""

    name: str
    path: Path


@dataclass
class BinaryArtifact(Resource):
    """A subclass of a resource that represents a binary artifact."""


@dataclass
class LibraryArtifact(Resource):
    """A subclass of a resource that represents a library artifact."""


def resource(*, name: str, path: str | Path, project: Project | None = None) -> Resource:
    """Creates a task for the purpose of carrying a :class:`Resource` descriptor."""

    project = project or Project.current()
    resource = Resource(name, project.directory / path)
    task = project.do(name, VoidTask)
    task.outputs.append(resource)
    return resource
