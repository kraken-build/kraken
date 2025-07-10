from os import fspath
from pathlib import Path
from typing import Protocol

from attr import dataclass


class Artifact(Protocol):
    """
    Base class for artifacts. Artifacts are objects, most often paths on a file system, that can be produced and
    consumed by tasks, allowing to construct a DAG.
    """

    def __hash__(self) -> int: ...

    def __eq__(self, other: object) -> bool: ...

    def exists(self) -> bool: ...


@dataclass(frozen=True, repr=False)
class PathArtifact:
    """
    Represents a path as an artifact on the local filesystem. Can only be created from absolute paths.
    """

    path: Path

    def __post_init__(self) -> None:
        if not self.path.is_absolute() or self.path != self.path.resolve(strict=False):
            raise ValueError(f"Only absolute, resolved paths can be used, got {self.path!r}")

    def __repr__(self) -> str:
        return f"PathArtifact(path={fspath(self.path)!r})"

    @staticmethod
    def of(path: str | Path) -> "PathArtifact":
        return PathArtifact(Path(path).absolute().resolve(strict=False))

    def exists(self) -> bool:
        return self.path.exists()
