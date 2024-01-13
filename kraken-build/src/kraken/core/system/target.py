""" A target is a logical unit of data that augments the build system and is used to derive other targets. Targets
can be stored in a project directly. Further targets may be inferred automatically from those via rules. A target does
not always imply an action that needs to be performed (e.g. multiple actions may be performed on the same target,
such as linting, formatting and compiling). An action may also consider multiple targets (such as a test runner that
runs tests in a project with multiple configurations may source both, the test files and configurations, from multiple
targets each).

The target API is considered experimental and may change at any time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from kraken.core.system.kraken_object import KrakenObject

if TYPE_CHECKING:
    from kraken.core.system.project import Project

T_Target = TypeVar("T_Target", bound="Target", contravariant=True)


class Target:
    """Base class for target objects. A target _must_ be a frozen dataclass that is hashable."""


class NamedTarget(KrakenObject, Generic[T_Target]):
    """A box that contains a reference to the target object. This is used to store a target by name in a project."""

    def __init__(self, name: str, project: Project, data: T_Target) -> None:
        super().__init__(name, project)
        self.data = data

    def __repr__(self) -> str:
        return f"NamedTarget(name={self.name!r}, data={self.data})"

    @property
    def project(self) -> Project:
        from kraken.core.system.project import Project

        assert isinstance(self._parent, Project)
        return self._parent
