""" This module provides the :class:`Task` class which represents a unit of work that is configurable through
:class:`Properties <Property>` that represent input/output parameters and are used to construct a dependency
graph."""

from __future__ import annotations

import abc
import contextlib
import dataclasses
import enum
import logging
import shlex
from collections.abc import Collection, Iterable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, ForwardRef, Generic, Literal, TypeVar, cast, overload

from deprecated import deprecated

from kraken.common import Supplier
from kraken.core.address import Address
from kraken.core.system.kraken_object import KrakenObject
from kraken.core.system.property import Property, PropertyContainer
from kraken.core.system.task_supplier import TaskSupplier

if TYPE_CHECKING:
    from kraken.core.system.project import Project
else:
    # Type hint evaluation in typeapi tries to fully resolve forward references to a type. In order to allow the
    # property evaluation happening in the PropertyContainer base class for the Task class, we need to make sure the
    # name "Project" resolves to something valid at runtime.
    Project = ForwardRef("object")


T = TypeVar("T")
T_Task = TypeVar("T_Task", bound="Task")
logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _Relationship(Generic[T]):
    """Represents a relationship to another task."""

    other_task: T
    strict: bool
    inverse: bool


TaskRelationship = _Relationship["Task"]
RelationshipMode = Literal["strict", "order-only"]


class TaskStatusType(enum.Enum):
    """Represents the possible statuses that a task can return from its execution."""

    PENDING = enum.auto()  #: The task is pending execution (only to be returned from :meth:`Task.prepare`).
    FAILED = enum.auto()  #: The task failed it's preparation or execution.
    INTERRUPTED = enum.auto()  #: The task was interrupted by the user.
    SUCCEEDED = enum.auto()  #: The task succeeded it's execution (only to be returned from :meth:`Task.execute`).
    STARTED = enum.auto()  #: The task started a background task that needs to be torn down later.
    SKIPPED = enum.auto()  #: The task was skipped (i.e. it is not applicable).
    UP_TO_DATE = enum.auto()  #: The task is up to date and did not run (or not run it's usual logic).
    WARNING = enum.auto()  #: The task succeeded, but with warnings (only to be returned from :meth:`Task.execute`).

    def is_ok(self) -> bool:
        return not self.is_not_ok()

    def is_not_ok(self) -> bool:
        return self in (TaskStatusType.PENDING, TaskStatusType.FAILED, TaskStatusType.INTERRUPTED)

    def is_pending(self) -> bool:
        return self == TaskStatusType.PENDING

    def is_failed(self) -> bool:
        return self == TaskStatusType.FAILED

    def is_interrupted(self) -> bool:
        return self == TaskStatusType.INTERRUPTED

    def is_succeeded(self) -> bool:
        return self == TaskStatusType.SUCCEEDED

    def is_started(self) -> bool:
        return self == TaskStatusType.STARTED

    def is_skipped(self) -> bool:
        return self == TaskStatusType.SKIPPED

    def is_up_to_date(self) -> bool:
        return self == TaskStatusType.UP_TO_DATE

    def is_warning(self) -> bool:
        return self == TaskStatusType.WARNING


@dataclasses.dataclass
class TaskStatus:
    """Represents a task status with a message."""

    type: TaskStatusType
    message: str | None

    def is_ok(self) -> bool:
        return self.type.is_ok()

    def is_not_ok(self) -> bool:
        return self.type.is_not_ok()

    def is_pending(self) -> bool:
        return self.type == TaskStatusType.PENDING

    def is_failed(self) -> bool:
        return self.type == TaskStatusType.FAILED

    def is_interrupted(self) -> bool:
        return self.type == TaskStatusType.INTERRUPTED

    def is_succeeded(self) -> bool:
        return self.type == TaskStatusType.SUCCEEDED

    def is_started(self) -> bool:
        return self.type == TaskStatusType.STARTED

    def is_skipped(self) -> bool:
        return self.type == TaskStatusType.SKIPPED

    def is_up_to_date(self) -> bool:
        return self.type == TaskStatusType.UP_TO_DATE

    def is_warning(self) -> bool:
        return self.type == TaskStatusType.WARNING

    @staticmethod
    def pending(message: str | None = None) -> TaskStatus:
        return TaskStatus(TaskStatusType.PENDING, message)

    @staticmethod
    def failed(message: str | None = None) -> TaskStatus:
        return TaskStatus(TaskStatusType.FAILED, message)

    @staticmethod
    def interrupted(message: str | None = None) -> TaskStatus:
        return TaskStatus(TaskStatusType.INTERRUPTED, message)

    @staticmethod
    def succeeded(message: str | None = None) -> TaskStatus:
        return TaskStatus(TaskStatusType.SUCCEEDED, message)

    @staticmethod
    def started(message: str | None = None) -> TaskStatus:
        return TaskStatus(TaskStatusType.STARTED, message)

    @staticmethod
    def skipped(message: str | None = None) -> TaskStatus:
        return TaskStatus(TaskStatusType.SKIPPED, message)

    @staticmethod
    def up_to_date(message: str | None = None) -> TaskStatus:
        return TaskStatus(TaskStatusType.UP_TO_DATE, message)

    @staticmethod
    def warning(message: str | None = None) -> TaskStatus:
        return TaskStatus(TaskStatusType.WARNING, message)

    @staticmethod
    def from_exit_code(command: list[str] | None, code: int) -> TaskStatus:
        return TaskStatus(
            TaskStatusType.SUCCEEDED if code == 0 else TaskStatusType.FAILED,
            None
            if code == 0 or command is None
            else 'command "' + " ".join(map(shlex.quote, command)) + f'" returned exit code {code}',
        )


@dataclasses.dataclass(frozen=True)
class TaskTag:
    name: str
    reason: str
    origin: str | None = None


class Task(KrakenObject, PropertyContainer, abc.ABC):
    """
    A Kraken Task is a unit of work that can be executed.

    Tasks goe through a number of stages during its lifetime:

    * Creation and configuration
    * Finalization (:meth:`finalize`) -- Mutations to properties of the task are locked after this.
    * Preparation (:meth:`prepare`) -- The task prepares itself for execution; it may indicate that it
        does not need to be executed at this state.
    * Execution (:meth:`execute`) -- The task executes its logic.

    Tasks are uniquely identified by their name and the project they belong to, which is also represented
    by the tasks's :property:`address`. Relationhips to other tasks can be added via the :meth:`depends_on`
    and `required_by` methods, or by passing properties of one task into the properties of another.
    """

    #: A human readable description of the task's purpose. This is displayed in the terminal upon
    #: closer inspection of a task.
    description: str | None = None

    #: Whether the task executes by default when no explicit task is selected to run on the command-line.
    default: bool = False

    #: Whether the task was explicitly selected on the command-line.
    selected: bool = False

    #: A logger that is bound to the task's address. Use this logger to log messages related to the task,
    #: for example when implementing :meth:`finalize`, :meth:`prepare` or :meth:`execute`.
    logger: logging.Logger

    def __init__(self, name: str, project: Project) -> None:
        from kraken.core.system.project import Project

        assert isinstance(name, str), type(name)
        assert isinstance(project, Project), type(project)
        KrakenObject.__init__(self, name, project)
        PropertyContainer.__init__(self)
        self.logger = logging.getLogger(f"{str(self.address)} [{type(self).__module__}.{type(self).__qualname__}]")
        self._outputs: list[Any] = []
        self.__tags: dict[str, set[TaskTag]] = {}
        self.__relationships: list[_Relationship[Address | Task]] = []

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.address})"

    @property
    def project(self) -> Project:
        """
        A convenient alias for :attr:`parent` which is a lot easier to understand when reading the code.
        """

        from kraken.core.system.project import Project

        assert isinstance(self._parent, Project), "Task.parent must be a Project"
        return self._parent

    ###
    # Begin: Deprecated APIs
    ###

    @property
    @deprecated(reason="Task.path is deprecated, use str(Task.address) instead.")
    def path(self) -> str:
        return str(self.address)

    @property
    @deprecated(reason="Task.outputs is deprecated.")
    def outputs(self) -> list[Any]:
        return self._outputs

    @deprecated(reason="Task.add_relationship() is deprecated, use Task.depends_on() or Task.required_by() instead.")
    def add_relationship(
        self,
        task_or_selector: Task | Sequence[Task | Address] | Address | str,
        strict: bool = True,
        inverse: bool = False,
    ) -> None:
        """Add a relationship to this task that will be returned by :meth:`get_relationships`.

        :param task_or_selector: A task, list of tasks or a task selector (wich may expand to multiple tasks)
            to add as a relationship to this task. If a task selector string is specified, it will be evaluated
            lazily when :meth:`get_relationships` is called.
        :param strict: Whether the relationship is strict, i.e. informs a strong dependency in one or the other
            direction. If a relationship is not strict, it informs only order of execution and parallel
            exclusivity.
        :param inverse: Whether to invert the relationship.
        """

        if isinstance(task_or_selector, (Task, str)):
            if isinstance(task_or_selector, str):
                task_or_selector = Address(task_or_selector)
            self.__relationships.append(_Relationship(task_or_selector, strict, inverse))
        elif isinstance(task_or_selector, Sequence):
            for idx, task in enumerate(task_or_selector):
                if not isinstance(task, Task):
                    raise TypeError(
                        f"task_or_selector[{idx}] must be Task | Sequence[Task] | str, got "
                        f"{type(task_or_selector).__name__}"
                    )
            for task in task_or_selector:
                if isinstance(task, str):
                    task = Address(task)
                self.__relationships.append(_Relationship(task, strict, inverse))
        else:
            raise TypeError(
                f"task_or_selector argument must be Task | Sequence[Task] | str, got {type(task_or_selector).__name__}"
            )

    def add_tag(self, name: str, *, reason: str, origin: str | None = None) -> None:
        """
        Add a tag to this task. The built-in tag "skip" is used to indicate that a task should not be executed.
        """

        if name not in self.__tags:
            self.__tags[name] = set()

        logger.debug("Adding tag %r (reason: %r, origin: %r) to %s", name, reason, origin, self.address)
        self.__tags[name].add(TaskTag(name, reason, origin))

    def remove_tag(self, tag: TaskTag) -> None:
        """
        Remove a tag from the task. If the tag does not exist, this is a no-op.
        """

        try:
            self.__tags[tag.name].discard(tag)
        except KeyError:
            logger.debug("Attempted to remove tag %r from %s, but it does not exist", tag, self.address)
            pass
        else:
            logger.debug("Removed tag %r from %s", tag, self.address)

    def get_tags(self, name: str) -> Collection[TaskTag]:
        """
        Get all tags of the specified name.
        """

        return self.__tags.get(name, set())

    # End: Deprecated APIs

    def depends_on(
        self, *tasks: Task | Address | str, mode: RelationshipMode = "strict", _inverse: bool = False
    ) -> None:
        """
        Declare that this task depends on the specified other tasks. Relationships are lazy, meaning references
        to tasks using an address will be evaluated when :meth:`get_relationships` is called.

        If the *mode* is set to `strict`, the relationship is considered a strong dependency, meaning that the
        dependent task must be executed after the dependency. If the *mode* is set to `order-only`, the relationship
        indicates only the order in which the tasks must be executed if both were to be executed in the same run.
        """

        for idx, task in enumerate(tasks):
            if isinstance(task, str):
                task = Address(task)
            if not isinstance(task, Address | Task):
                raise TypeError(f"tasks[{idx}] must be Address | Task | str, got {type(task).__name__}")
            self.__relationships.append(_Relationship(task, mode == "strict", _inverse))

    def required_by(self, *tasks: Task | Address | str, mode: RelationshipMode = "strict") -> None:
        """
        Declare that this task is required by the specified other tasks. This is the inverse of :meth:`depends_on`,
        effectively declaring the same relationship in the opposite direction.
        """

        self.depends_on(*tasks, mode=mode, _inverse=True)

    def get_properties(self) -> Iterable[Property[Any]]:
        for key in self.__schema__:
            property: Property[Any] = getattr(self, key)
            yield property

    def get_relationships(self) -> Iterable[TaskRelationship]:
        """
        Return an iterable that yields all relationships that this task has to other tasks as indicated by
        information available in the task itself. The method will not return relationships established to
        this task from other tasks.

        The iterable will contain every relationship that is declared via :meth:`depends_on` or :meth:`required_by`,
        as well as relationships that are implied by the task's properties. For example, if a property of this
        task is set to the value of a property of another task, a relationship is implied between the tasks.
        """

        # Derive dependencies through property lineage.
        for property in self.get_properties():
            for supplier, _ in property.lineage():
                if supplier is property:
                    continue
                if isinstance(supplier, Property) and isinstance(supplier.owner, Task) and supplier.owner is not self:
                    yield TaskRelationship(supplier.owner, True, False)
                if isinstance(supplier, TaskSupplier):
                    yield TaskRelationship(supplier.get(), True, False)

        # Manually added relationships.
        for rel in self.__relationships:
            if isinstance(rel.other_task, Address):
                try:
                    resolved_tasks = self.project.context.resolve_tasks([rel.other_task], relative_to=self.project)
                except ValueError as exc:
                    raise ValueError(f"in task {self.address}: {exc}")
                for task in resolved_tasks:
                    yield TaskRelationship(task, rel.strict, rel.inverse)
            else:
                assert isinstance(rel.other_task, Task)
                yield cast(TaskRelationship, rel)

    def get_description(self) -> str | None:
        """
        Return the task's description. The default implementation formats the :attr:`description` string with the
        task's properties. Any Path property will be converted to a relative string to assist the reader.
        """

        class _MappingProxy:
            def __getitem__(_, key: str) -> Any:
                if key not in type(self).__schema__:
                    return f"%({key})s"
                prop = getattr(self, key)
                try:
                    value = prop.get()
                except Supplier.Empty:
                    return "<empty>"
                else:
                    if isinstance(value, Path):
                        try:
                            value = value.relative_to(Path.cwd())
                        except ValueError:
                            pass
                    return value

        if self.description:
            return self.description % _MappingProxy()
        return None

    @overload
    def get_outputs(self) -> Iterable[Any]:
        """Iterate over all outputs of the task. This includes all outputs in :attr:`Task.outputs` and the values
        in all properties defines as outputs. All output properties that return a sequence will be flattened.

        This should be called only after the task was executed, otherwise the output properties are likely empty
        and will error when read."""

    @overload
    def get_outputs(self, output_type: type[T]) -> Iterable[T]:
        """Iterate over all outputs of the task of the specified *output_type*. If a property provides a sequence of
        values of the *output_type*, that list is flattened.

        This should be called only after the task was executed, otherwise the output properties are likely empty
        and will error when read.

        :param output_type: The output type to search for."""

    # @deprecated(reason="Rely on the target-rule system to derive the artifacts of a task.")
    def get_outputs(self, output_type: type[T] | type[object] = object) -> Iterable[T] | Iterable[Any]:
        results = []

        for property_name, property_desc in self.__schema__.items():
            if not property_desc.is_output:
                continue
            property: Property[Any] = getattr(self, property_name)
            if property.provides(output_type):
                results += property.get_of_type(output_type)

        for obj in self.outputs:
            if isinstance(obj, output_type):
                results.append(obj)

        return results

    def finalize(self) -> None:
        """
        This method is called by :meth:`Context.finalize()`. It gives the task a chance update its
        configuration before the build process is executed. The default implementation finalizes all non-output
        properties, preventing them to be further mutated.
        """

        for key in self.__schema__:
            prop: Property[Any] = getattr(self, key)
            if not self.__schema__[key].is_output:
                prop.finalize()

    def prepare(self) -> TaskStatus | None:
        """
        Called before a task is executed. This is called from the main process to check for example if the task
        is skippable or up to date. The implementation of this method should be quick to determine the task status,
        otherwise it should be done in :meth:`execute`.

        This method should not return :attr:`TaskStatusType.SUCCEEDED` or :attr:`TaskStatusType.FAILED`. If `None`
        is returned, it is assumed that the task is :attr:`TaskStatusType.PENDING`.
        """

        return TaskStatus.pending()

    @abc.abstractmethod
    def execute(self) -> TaskStatus | None:
        """
        Implements the behaviour of the task. The task can assume that all strict dependencies have been executed
        successfully. Output properties of dependency tasks that are only written by the task's execution are now
        accessible.

        This method should not return :attr:`TaskStatusType.PENDING`. If `None` is returned, it is assumed that the
        task is :attr:`TaskStatusType.SUCCEEDED`. If the task fails, it should return :attr:`TaskStatusType.FAILED`.
        If an exception is raised during this method, the task status is also assumed to be
        :attr:`TaskStatusType.FAILED`. If the task finished successfully but with warnings, it should return
        :attr:`TaskStatusType.WARNING`.
        """

        raise NotImplementedError

    def teardown(self) -> TaskStatus | None:
        """
        This method is called only if the task returns :attr:`TaskStatusType.STARTED` from :meth:`execute`. It is
        called if _all_ direct dependants of the task have been executed (whether successfully or not) or if no further
        task execution is queued.
        """

        return None


class GroupTask(Task):
    """This task can be used to group tasks under a common name. Ultimately it is just another task that depends on
    the tasks in the group, forcing them to be executed when this task is targeted. Group tasks are not enabled
    by default."""

    tasks: list[Task]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.tasks = []
        self.default = False

    def add(self, tasks: str | Task | Iterable[str | Task]) -> None:
        """Add one or more tasks by name or task object to this group.

        This is different from adding a task via :meth:`add_relationship` because the task is instead stored in the
        :attr:`tasks` list which can be used to access the members of the task. Relationships for a group task can
        still be used to express relationships between groups or tasks and groups.

        Also note that :meth:`add_relationship` supports lazy evaluation of task selectors, whereas using this method
        to add a task to the group by a selector string requires that the task already exists.
        """

        if isinstance(tasks, (str, Task)):
            tasks = [tasks]

        for task in tasks:
            if isinstance(task, str):
                self.tasks += [
                    t for t in self.project.context.resolve_tasks([task], self.project) if t not in self.tasks
                ]
            elif task not in self.tasks:
                self.tasks.append(task)

    # Task

    def get_outputs(self, output_type: type[T] | type[object] = object) -> Iterable[T] | Iterable[Any]:
        yield from super().get_outputs(output_type)
        for task in self.tasks:
            yield from task.get_outputs(output_type)

    def get_relationships(self) -> Iterable[TaskRelationship]:
        for task in self.tasks:
            yield TaskRelationship(task, True, False)
        yield from super().get_relationships()

    def prepare(self) -> TaskStatus | None:
        return TaskStatus.skipped("is a GroupTask")

    def execute(self) -> TaskStatus | None:
        raise RuntimeError("GroupTask cannot be executed")


class VoidTask(Task):
    """This task does nothing and can always be skipped."""

    skip: Property[bool] = Property.default(True)
    message: Property[str] = Property.default("is a VoidTask")

    def prepare(self) -> TaskStatus | None:
        if self.skip.get():
            return TaskStatus.skipped(self.message.get())
        return TaskStatus.pending()

    def execute(self) -> TaskStatus | None:
        pass


class BackgroundTask(Task):
    """This base class represents a task that starts some process in the background that keeps running which is
    then terminated when all direct dependant tasks are completed and no work is left. A common use case for this
    type of task is to spawn sidecar processes which are relied on by other tasks to be available during their
    execution."""

    @abc.abstractmethod
    def start_background_task(self, exit_stack: contextlib.ExitStack) -> TaskStatus | None:
        """Start some task or process in the background. Use the *exit_stack* to ensure cleanup of your allocated
        resources in case of an unexpected error or when the background task is torn down. Returning not-None and
        not :attr:`TaskStatusType.STARTED`, or causing an exception will immediately close the exit stack."""

        raise NotImplementedError

    def __del__(self) -> None:
        try:
            self.__exit_stack
        except AttributeError:
            pass
        else:
            logger.warning(
                'BackgroundTask.teardown() did not get called on task "%s". This may cause some issues, such '
                "as an error during serialization or zombie processes.",
                self.address,
            )

    # Task

    def execute(self) -> TaskStatus | None:
        self.__exit_stack = contextlib.ExitStack()
        try:
            status = self.start_background_task(self.__exit_stack)
            if status is None:
                status = TaskStatus.started()
            elif not status.is_started():
                self.__exit_stack.close()
            return status
        except BaseException:
            self.__exit_stack.close()
            raise

    def teardown(self) -> None:
        self.__exit_stack.close()
        del self.__exit_stack


class TaskSet(Collection[Task]):
    """Represents a collection of tasks."""

    def __init__(self, tasks: Iterable[Task] = ()) -> None:
        self._tasks = set(tasks)
        self._partition_to_task_map: dict[str, set[Task]] = {}
        self._task_to_partition_map: dict[Task, set[str]] = {}

    def __iter__(self) -> Iterator[Task]:
        return iter(self._tasks)

    def __len__(self) -> int:
        return len(self._tasks)

    def __repr__(self) -> str:
        return f"TaskSet(length={len(self._tasks)})"

    def __contains__(self, __x: object) -> bool:
        return __x in self._tasks

    def add(self, tasks: Iterable[Task], *, partition: str | None = None) -> None:
        """Add the given *tasks* to the set.

        :param tasks: The tasks to add.
        :param partition: If specified, this will register the *tasks* under the given string as a "partition"
            within the set. This is used by :meth:`Project.resolve_tasks` to store which tasks were resolved
            through which task selector string. Later, this can be used to map a task back to the selector it
            was resolved from."""

        tasks = set(tasks)
        self._tasks.update(tasks)
        if partition is not None:
            self._partition_to_task_map.setdefault(partition, set()).update(tasks)
            for task in tasks:
                self._task_to_partition_map.setdefault(task, set()).add(partition)

    def select(self, output_type: type[T]) -> TaskSetSelect[T]:
        """Resolve outputs of the given tasks and return them as a dictionary mapping from task to the values. This
        should only be called after the given tasks have been executed, otherwise the outputs are likely not set.
        Use :meth:`resolve_outputs_supplier` to create a :class:`Supplier` that delegates to this method when it is
        retrieved.

        In addition to looking at output properties, this also includes elements contained in :attr:`Task.output`."""

        return TaskSetSelect(self, output_type)

    def partitions(self) -> TaskSetPartitions:
        """Return a helper class to access the partitions in the set."""

        return TaskSetPartitions(self._partition_to_task_map, self._task_to_partition_map)


class TaskSetSelect(Generic[T]):
    """Represents a select statement of outputs from a set of tasks."""

    def __init__(self, tasks: TaskSet, output_type: type[T]) -> None:
        self._tasks = tasks
        self._output_type = output_type

    def all(self) -> Iterable[T]:
        for task in self._tasks:
            yield from task.get_outputs(self._output_type)

    def dict_supplier(self) -> Supplier[dict[Task, list[T]]]:
        return Supplier.of_callable(lambda: self.dict(), [TaskSupplier(x) for x in self._tasks])

    def supplier(self) -> Supplier[list[T]]:
        return Supplier.of_callable(lambda: list(self.all()), [TaskSupplier(x) for x in self._tasks])

    def dict(self) -> dict[Task, list[T]]:
        results: dict[Task, list[T]] = {}
        for task in self._tasks:
            results[task] = list(task.get_outputs(self._output_type))
        return results


class TaskSetPartitions:
    """Helper class to operate on the partitions of a task set."""

    def __init__(
        self, partitions_to_task_map: dict[str, set[Task]], task_to_partitions_map: dict[Task, set[str]]
    ) -> None:
        self._ptt = partitions_to_task_map
        self._ttp = task_to_partitions_map

    def __len__(self) -> int:
        return len(self._ptt)

    def __iter__(self) -> Iterable[str]:
        return iter(self._ptt)

    @overload
    def __getitem__(self, partition: str) -> Collection[Task]:
        ...

    @overload
    def __getitem__(self, partition: Task) -> Collection[str]:
        ...

    def __getitem__(self, partition: str | Task) -> Collection[str] | Collection[Task]:
        if isinstance(partition, str):
            return self._ptt.get(partition) or ()
        else:
            return self._ttp.get(partition) or ()
