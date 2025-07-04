from __future__ import annotations

import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload

from kraken.core.base import Currentable, MetadataContainer
from kraken.core.system.kraken_object import KrakenObject
from kraken.core.system.task import GroupTask, Task

if TYPE_CHECKING:
    from kraken.core.system.context import Context

T = TypeVar("T")
T_Task = TypeVar("T_Task", bound="Task")


class TaskNotFound(Exception):
    pass


class DuplicateMember(Exception):
    pass


class Project(KrakenObject, MetadataContainer, Currentable["Project"]):
    """A project consolidates tasks related to a directory on the filesystem."""

    directory: Path
    context: Context
    metadata: list[Any]  #: A list of arbitrary objects that are usually looked up by type.

    def __init__(self, name: str, directory: Path, parent: Project | None, context: Context) -> None:
        assert isinstance(name, str), type(name)
        assert isinstance(directory, Path), type(directory)
        assert isinstance(parent, Project) or parent is None, type(parent)
        KrakenObject.__init__(self, name, parent)
        MetadataContainer.__init__(self)
        Currentable.__init__(self)

        self.directory = directory
        self.context = context
        self.metadata = []

        # We store all members that can be referenced by a fully qualified name in the same dictionary to ensure
        # we're not accidentally allocating the same name twice.
        self._members: dict[str, Task | Project] = {}

        apply_group = self.group(
            "apply", description="Tasks that perform automatic updates to the project consistency."
        )
        fmt_group = self.group("fmt", description="Tasks that that perform code formatting operations.")
        fmt_group.depends_on(apply_group, mode="strict")

        check_group = self.group("check", description="Tasks that perform project consistency checks.", default=True)

        gen_group = self.group("gen", description="Tasks that perform code generation.", default=True)

        lint_group = self.group("lint", description="Tasks that perform code linting.", default=True)
        lint_group.depends_on(check_group, mode="strict")
        lint_group.depends_on(gen_group, mode="strict")

        build_group = self.group("build", description="Tasks that produce build artefacts.")
        build_group.depends_on(lint_group, mode="order-only")
        build_group.depends_on(gen_group, mode="strict")

        audit_group = self.group("audit", description="Tasks that perform auditing on built artefacts and code")
        audit_group.depends_on(build_group, mode="strict")
        audit_group.depends_on(gen_group, mode="strict")

        test_group = self.group("test", description="Tasks that perform unit tests.", default=True)
        test_group.depends_on(build_group, mode="order-only")
        test_group.depends_on(gen_group, mode="strict")

        integration_test_group = self.group("integrationTest", description="Tasks that perform integration tests.")
        integration_test_group.depends_on(test_group, mode="order-only")
        integration_test_group.depends_on(gen_group, mode="strict")

        publish_group = self.group("publish", description="Tasks that publish build artefacts.")
        publish_group.depends_on(integration_test_group, mode="order-only")
        publish_group.depends_on(build_group, mode="strict")

        deploy_group = self.group("deploy", description="Tasks that deploy applications.")
        deploy_group.depends_on(publish_group, mode="order-only")

        self.group("update", description="Tasks that update dependencies of the project.")

    def __repr__(self) -> str:
        return f"Project({self.address})"

    @property
    def parent(self) -> Project | None:
        if self._parent is None:
            return None
        assert isinstance(self._parent, Project), "Project.parent must be a Project"
        return self._parent

    @property
    def name(self) -> str:
        if self.address.is_root():
            warnings.warn(
                "Accessing Project.name on the root project is deprecated since kraken-core v0.12.0. "
                "In future versions, this will result ValueError being raised. The project name is now "
                "determined by the Address.name, which is undefined on the root address (`:`). "
                "The fallback behaviour for this version is that we return the Project.directory.name.",
                DeprecationWarning,
            )
            return self.directory.name
        return self.address.name

    @property
    def build_directory(self) -> Path:
        """Returns the recommended build directory for the project; this is a directory inside the context
        build directory amended by the project name."""

        return self.context.build_directory / str(self.address).replace(":", "/").lstrip("/")

    @overload
    def task(self, name: str, /) -> Task:
        """
        Get a task from the project by name. Raises a #TaskNotFound exception if the task does not exist.
        """

    @overload
    def task(
        self,
        name: str,
        type_: type[T_Task],
        /,
        *,
        default: bool | None = None,
        group: str | GroupTask | None = None,
        description: str | None = None,
    ) -> T_Task:
        """
        Create a new task in the project with the specified name. If a member of the project with the same name already
        exists, a #DuplicateMember exception is raised.
        """

    def task(
        self,
        name: str,
        type_: type[T_Task] | None = None,
        /,
        *,
        default: bool | None = None,
        group: str | GroupTask | None = None,
        description: str | None = None,
    ) -> Task | T_Task:
        if type_ is None:
            assert default is None
            assert group is None
            assert description is None

            try:
                task = self._members[name]
                if not isinstance(task, Task):
                    raise KeyError("Not a task")
            except KeyError:
                raise TaskNotFound(self.address.concat(name))
            return task

        if type_ is None or not isinstance(type_, type) or not issubclass(type_, Task):
            raise TypeError(f"Expected a Task type, got {type(type_).__name__}")

        if name in self._members:
            raise DuplicateMember(f"{self} already has a member {name!r}")

        task = type_(name, self)
        if default is not None:
            task.default = default

        match group:
            case str():
                self.group(group).add(task)
            case GroupTask():
                group.add(task)
            case None:
                pass
            case _:
                raise TypeError(f"Expected str or GroupTask, got {type(group)}")

        if description is not None:
            task.description = description

        self._members[name] = task
        return task

    def tasks(self) -> Mapping[str, Task]:
        return {t.name: t for t in self._members.values() if isinstance(t, Task)}

    def subprojects(self) -> Mapping[str, Project]:
        return {p.name: p for p in self._members.values() if isinstance(p, Project)}

    @overload
    def subproject(self, name: str, mode: Literal["empty", "execute"] = "execute") -> Project:
        """
        Mount a sub-project of this project with the specified *name*.

        :param name: The name of the sub-project. The address of the returned project will be the current project's
            address appended by the given *name*. The name must not contain special characters reserved to the Address
            syntax. The sub-project will be bound to the directory with the same *name* in the directory of the current
            project.
        :param mode: Specifies how the project should be created. If set to "empty", the project will be created
            without loading any build scripts. If set to "execute" (default), the project will be created and its
            build scripts will be executed.
        """

    @overload
    def subproject(self, name: str, mode: Literal["if-exists", "or-none"]) -> Project | None:
        """
        Mount a sub-project of this project with the specified *name* and execute it if the directory matching the
        *name* exists. If such a directory does not exist, no project is created and `None` is returned. If you want
        to create a project in any case, you can use this method, and if you get `None` back you can call
        #subproject() again with the *mode* set to "empty".

        Using the `"or-none"` mode, the sub-project will only be returned if it was already loaded.
        """

    def subproject(
        self,
        name: str,
        mode: Literal["empty", "execute", "if-exists", "or-none"] = "execute",
    ) -> Project | None:
        assert isinstance(mode, str), f"mode must be a string, got {type(mode).__name__}"

        obj = self._members.get(name)
        if obj is None and mode == "or-none":
            return None
        if obj is not None:
            if not isinstance(obj, Project):
                raise ValueError(
                    f"{self.address}:{name} does not refer to a project (got {type(obj).__name__} instead)"
                )
            return obj

        directory = self.directory / name
        if mode == "empty":
            project = Project(name, directory, self, self.context)
            self._members[name] = project
        elif mode == "execute" or mode == "if-exists":
            if not directory.is_dir():
                if mode == "if-exists":
                    return None
                raise FileNotFoundError(
                    f"{self.address}:{name} cannot be loaded because the directory {directory} does not exist"
                )
            project = self.context.load_project(directory, self, require_buildscript=False)
            assert name in self._members
            assert self._members[name] is project
        else:
            raise ValueError(f"invalid mode {mode!r}")

        return project

    def has_subproject(self, name: str) -> bool:
        """
        Returns `True` if *name* refers to a subproject that exists in the current project.
        """

        return isinstance(self._members.get(name), Project)

    def add_task(self, task: Task) -> None:
        """Adds a task to the project.

        Raises:
            ValueError: If a member with the same name already exists or if the task's project does not match
        """

        if task.name in self._members:
            raise ValueError(f"{self} already has a member {task.name!r}, cannot add {task}")
        if task.project is not self:
            raise ValueError(f"{task}.project mismatch")
        self._members[task.name] = task

    def add_child(self, project: Project) -> None:
        """Adds a project as a child project.

        Raises:
            ValueError: If a member with the same name already exists or if the project's parent does not match
        """

        if project.name in self._members:
            raise ValueError(f"{self} already has a member {project.name!r}, cannot add {project}")
        if project.parent is not self:
            raise ValueError(f"{project}.parent mismatch")
        self._members[project.name] = project

    def remove_child(self, project: Project) -> None:
        assert project.parent is self
        assert self._members[project.name] is project

        del self._members[project.name]

    def group(self, name: str, *, description: str | None = None, default: bool | None = None) -> GroupTask:
        """Create or get a group of the given name. If a task with the given name already exists, it must refer
        to a task of type :class:`GroupTask`, otherwise a :class:`RuntimeError` is raised.

        :param name: The name of the group in the project.
        :param description: If specified, set the group's description.
        :param default: Whether the task group is run by default."""

        task = self.tasks().get(name)
        if task is None:
            task = self.task(name, GroupTask)
        elif not isinstance(task, GroupTask):
            raise RuntimeError(f"{task.address!r} must be a GroupTask, but got {type(task).__name__}")
        if description is not None:
            task.description = description
        if default is not None:
            task.default = default

        return task
