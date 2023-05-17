from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional, Type, TypeVar, cast, overload

import builddsl
from deprecated import deprecated
from typing_extensions import Literal

from kraken.core.address import Address
from kraken.core.base import Currentable, MetadataContainer
from kraken.core.system.property import Property
from kraken.core.system.task import GroupTask, Task, TaskSet

if TYPE_CHECKING:
    from kraken.core.system.context import Context

T = TypeVar("T")
T_Task = TypeVar("T_Task", bound="Task")


class Project(MetadataContainer, Currentable["Project"]):
    """A project consolidates tasks related to a directory on the filesystem."""

    address: Address
    directory: Path
    parent: Optional[Project]
    context: Context
    metadata: list[Any]  #: A list of arbitrary objects that are usually looked up by type.

    def __init__(self, name: str, directory: Path, parent: Optional[Project], context: Context) -> None:
        self.address = parent.address.append(name) if parent else Address.ROOT
        self.directory = directory
        self.parent = parent
        self.context = context
        self.metadata = []

        # We store all members that can be referenced by a fully qualified name in the same dictionary to ensure
        # we're not accidentally allocating the same name twice.
        self._members: dict[str, Task | Project] = {}

        apply_group = self.group(
            "apply", description="Tasks that perform automatic updates to the project consistency."
        )
        fmt_group = self.group("fmt", description="Tasks that that perform code formatting operations.")
        fmt_group.add_relationship(apply_group, strict=True)

        check_group = self.group("check", description="Tasks that perform project consistency checks.", default=True)

        gen_group = self.group("gen", description="Tasks that perform code generation.", default=True)

        lint_group = self.group("lint", description="Tasks that perform code linting.", default=True)
        lint_group.add_relationship(check_group, strict=True)
        lint_group.add_relationship(gen_group, strict=True)

        build_group = self.group("build", description="Tasks that produce build artefacts.")
        build_group.add_relationship(lint_group, strict=False)
        build_group.add_relationship(gen_group, strict=True)

        audit_group = self.group("audit", description="Tasks that perform auditing on built artefacts and code")
        audit_group.add_relationship(build_group, strict=True)
        audit_group.add_relationship(gen_group, strict=True)

        test_group = self.group("test", description="Tasks that perform unit tests.", default=True)
        test_group.add_relationship(build_group, strict=False)
        test_group.add_relationship(gen_group, strict=True)

        integration_test_group = self.group("integrationTest", description="Tasks that perform integration tests.")
        integration_test_group.add_relationship(test_group, strict=False)
        integration_test_group.add_relationship(gen_group, strict=True)

        publish_group = self.group("publish", description="Tasks that publish build artefacts.")
        publish_group.add_relationship(integration_test_group, strict=False)
        publish_group.add_relationship(build_group, strict=True)

        deploy_group = self.group("deploy", description="Tasks that deploy applications.")
        deploy_group.add_relationship(publish_group, strict=False)

        self.group("update", description="Tasks that update dependencies of the project.")

    def __repr__(self) -> str:
        return f"Project({self.path})"

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

    # TODO(NiklasRosenstein): To be deprecated in v0.13.0
    @property
    def path(self) -> str:
        """Returns the path that uniquely identifies the project in the current build context."""

        return str(self.address)

    @property
    def build_directory(self) -> Path:
        """Returns the recommended build directory for the project; this is a directory inside the context
        build directory ammended by the project name."""

        return self.context.build_directory / self.path.replace(":", "/").lstrip("/")

    def task(self, name: str) -> Task:
        """Return a task in the project by name."""

        task = self._members[name]
        if not isinstance(task, Task):
            raise ValueError(f"name {name!r} does not refer to a task, but {type(task).__name__}")
        return task

    def tasks(self) -> Mapping[str, Task]:
        return {t.name: t for t in self._members.values() if isinstance(t, Task)}

    @deprecated(reason="use Project.subprojects() or Project.subproject() instead")
    def children(self) -> Mapping[str, Project]:
        return self.subprojects()

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
    def subproject(self, name: str, mode: Literal["if-exists"]) -> Project | None:
        """
        Mount a sub-project of this project with the specified *name* and execute it if the directory matching the
        *name* exists. If such a directory does not exist, no project is created and `None` is returned. If you want
        to create a project in any case, you can use this method, and if you get `None` back you can call
        #subproject() again with the *mode* set to "empty".
        """

    @overload
    @deprecated(reason="use the Project.subproject(mode) parameter instead")
    def subproject(self, name: str, mode: bool) -> Project | None:
        """
        This is a deprecated version that is semantically equivalent to calling #subproject() with the *mode*
        parameter set to "if-exists".
        """

    @overload
    @deprecated(reason="use the Project.subproject(mode) parameter instead")
    def subproject(self, name: str, *, load: bool) -> Project | None:
        """
        This is a deprecated version that is semantically equivalent to calling #subproject() with the *mode*
        parameter set to "if-exists".
        """

    def subproject(
        self,
        name: str,
        mode: bool | Literal["empty", "execute", "if-exists"] = "execute",
        *,
        load: bool | None = None,
    ) -> Project | None:
        if load is not None:
            warnings.warn("the `load` parameter is deprecated, use `mode` instead", DeprecationWarning)
        if isinstance(mode, bool):
            warnings.warn("the `load` parameter is deprecated, use `mode` instead", DeprecationWarning)
            mode = "execute" if mode else "if-exists"
        del load

        obj = self._members.get(name)
        if obj is None and mode == "if-exists":
            return None
        if obj is not None:
            if not isinstance(obj, Project):
                raise ValueError(f"{self.path}:{name} does not refer to a project (got {type(obj).__name__} instead)")
            return obj

        directory = self.directory / name
        if mode == "empty":
            project = Project(name, directory, self, self.context)
            self._members[name] = project
        elif mode == "execute":
            if not directory.is_dir():
                raise FileNotFoundError(
                    f"{self.path}:{name} cannot be loaded because the directory {directory} does not exist"
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

    def resolve_tasks(self, tasks: str | Task | Iterable[str | Task]) -> TaskSet:
        """Resolve tasks relative to the current project."""

        if isinstance(tasks, (str, Task)):
            tasks = [tasks]

        result = TaskSet()
        for item in tasks:
            if isinstance(item, str):
                result.add(self.context.resolve_tasks([item], self), partition=item)
            else:
                result.add([item])

        return result

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

    def do(
        self,
        name: str,
        task_type: Type[T_Task] = cast(Any, Task),
        default: bool | builddsl.UnboundClosure | None = None,
        *,
        group: str | GroupTask | None = None,
        description: str | None = None,
        **kwargs: Any,
    ) -> T_Task:
        """Add a task to the project under the given name, executing the specified action.

        :param name: The name of the task to add.
        :param task_type: The type of task to add.
        :param default: Override :attr:`Task.default`, or a closure to invoke with the created task.
        :param group: Add the task to the given group in the project.
        :param kwargs: Any number of properties to set on the task. Unknown properties will be ignored
            with a warning log.
        :return: The created task.
        """

        # NOTE(NiklasRosenstein): In versions prior to kraken-core 0.12.0, we did not validate task names.
        #       Now, the #Address class performs the validation and is rather strict. In order to not fully
        #       break usage of this function with invalid names, we convert the name to a valid form instead
        #       and issue a warning. This behaviour shall be removed in kraken-core 0.14.0.

        if not re.match(Address.Element.VALIDATION_REGEX, name):
            new_name = re.sub(f"[^{Address.Element.VALID_CHARACTERS}]+", "-", name)
            warnings.warn(
                f"Task name `{name}` is invalid and will be normalized to `{new_name}`. Starting with "
                "kraken-core 0.12.0, Task names must follow a stricter naming convention subject to the "
                f"Address class' validation (must match /{Address.Element.VALIDATION_REGEX}/).",
                DeprecationWarning,
                stacklevel=2,
            )
            name = new_name

        if name in self._members:
            raise ValueError(f"{self} already has a member {name!r}")

        task = task_type(name, self)
        if default is not None and not isinstance(default, builddsl.UnboundClosure):
            task.default = default
        if description is not None:
            task.description = description

        invalid_keys = set()
        for key, value in kwargs.items():
            prop = getattr(task, key, None)
            if isinstance(prop, Property):
                if value is not None:
                    prop.set(value)
            else:
                invalid_keys.add(key)
        if invalid_keys:
            task.logger.warning(
                "properties %s cannot be set because they don't exist (task %s)", invalid_keys, task.path
            )

        if isinstance(default, builddsl.UnboundClosure):
            default(task)
        self.add_task(task)
        if isinstance(group, str):
            group = self.group(group)
        if group is not None:
            group.add(task)
        return task

    def group(self, name: str, *, description: str | None = None, default: bool | None = None) -> GroupTask:
        """Create or get a group of the given name. If a task with the given name already exists, it must refer
        to a task of type :class:`GroupTask`, otherwise a :class:`RuntimeError` is raised.

        :param name: The name of the group in the project.
        :param description: If specified, set the group's description.
        :param default: Whether the task group is run by default."""

        task = self.tasks().get(name)
        if task is None:
            task = self.do(name, GroupTask)
        elif not isinstance(task, GroupTask):
            raise RuntimeError(f"{task.path!r} must be a GroupTask, but got {type(task).__name__}")
        if description is not None:
            task.description = description
        if default is not None:
            task.default = default

        return task
