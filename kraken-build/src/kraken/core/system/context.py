from __future__ import annotations

import collections
import dataclasses
import enum
import logging
from collections.abc import Callable, Iterable, Iterator, MutableMapping, Sequence
from pathlib import Path
from typing import Any, ClassVar, TypeAlias, TypeVar, cast, overload

from kraken.common import CurrentDirectoryProjectFinder, ProjectFinder, ScriptRunner
from kraken.common.iter import bipartition
from kraken.core.address import Address, AddressSpace, resolve_address
from kraken.core.base import Currentable, MetadataContainer
from kraken.core.system.errors import BuildError, ProjectLoaderError, ProjectNotFoundError
from kraken.core.system.executor import GraphExecutor, GraphExecutorObserver
from kraken.core.system.executor.default import (
    DefaultGraphExecutor,
    DefaultPrintingExecutorObserver,
    DefaultTaskExecutor,
)
from kraken.core.system.graph import TaskGraph
from kraken.core.system.project import Project
from kraken.core.system.task import Task

logger = logging.getLogger(__name__)
T = TypeVar("T")


class KrakenAddressSpace(AddressSpace["Project | Task"]):
    """
    Implements the navigation for address resolution in the addressable project and task namespace
    represented by a #Context and its root #Project.
    """

    def __init__(self, root_project: Project) -> None:
        self.root_project = root_project

    def get_root(self) -> Project:
        return self.root_project

    def get_parent(self, entity: Project | Task) -> Project | None:
        if isinstance(entity, Task):
            return entity.project
        return entity.parent

    def get_children(self, entity: Project | Task) -> Iterable[Project | Task]:
        if isinstance(entity, Project):
            yield from entity.subprojects().values()
            yield from entity.tasks().values()


class ContextEventType(enum.Enum):
    any = enum.auto()
    on_project_init = enum.auto()  # event data type is Project
    on_project_loaded = enum.auto()  # event data type is Project
    on_project_begin_finalize = enum.auto()  # event data type is Project
    on_project_finalized = enum.auto()  # event data type is Project
    on_context_begin_finalize = enum.auto()  # event data type is Context
    on_context_finalized = enum.auto()  # event data type is Context


@dataclasses.dataclass
class ContextEvent:
    Type: ClassVar[TypeAlias] = ContextEventType
    Listener = Callable[["ContextEvent"], Any]
    T_Listener = TypeVar("T_Listener", bound=Listener)

    type: Type
    data: Any  # Depends on the event type


class TaskResolutionException(Exception):
    pass


class Context(MetadataContainer, Currentable["Context"]):
    """This class is the single instance where all components of a build process come together."""

    #: The focus project is the one that maps to the current working directory when invoking kraken.
    #: Kraken may be invoked in a directory that does not map to a project, in which case this is None.
    focus_project: Project | None = None

    def __init__(
        self,
        build_directory: Path,
        project_finder: ProjectFinder | None = None,
        executor: GraphExecutor | None = None,
        observer: GraphExecutorObserver | None = None,
    ) -> None:
        """
        :param build_directory: The directory in which all files generated during the build should be stored.
        :param project_finder: This project finder should only search within the directory it was given, not
            around or in parent folders. Defaults to :class:`CurrentDirectoryProjectFinder`.
        :param executor: The executor to use when the graph is executed.
        :param observer: The executro observer to use when the graph is executed.
        """

        super().__init__()
        self.build_directory = build_directory
        self.project_finder = project_finder or CurrentDirectoryProjectFinder.default()
        self.executor = executor or DefaultGraphExecutor(DefaultTaskExecutor())
        self.observer = observer or DefaultPrintingExecutorObserver()
        self._finalized: bool = False
        self._root_project: Project | None = None
        self._listeners: MutableMapping[ContextEvent.Type, list[ContextEvent.Listener]] = collections.defaultdict(list)
        self.focus_project: Project | None = None

    @property
    def root_project(self) -> Project:
        assert self._root_project is not None, "Context.root_project is not set"
        return self._root_project

    @root_project.setter
    def root_project(self, project: Project) -> None:
        assert self._root_project is None, "Context.root_project is already set"
        self._root_project = project

    def load_project(
        self,
        directory: Path,
        parent: Project | None = None,
        require_buildscript: bool = True,
        runner: ScriptRunner | None = None,
        script: Path | None = None,
    ) -> Project:
        """Loads a project from a file or directory.

        :param directory: The directory to load the project from.
        :param parent: The parent project. If no parent is specified, then the :attr:`root_project`
            must not have been initialized yet and the loaded project will be initialize it.
            If the root project is initialized but no parent is specified, an error will be
            raised.
        :param require_buildscript: If set to `True`, a build script must exist in *directory*.
            Otherwise, it will be accepted if no build script exists in the directory.
        :param runner: If the :class:`ScriptRunner` for this project is already known, it can be passed here.
        :param script: If the script to load for the project is already known, it can be passed here. Cannot be
            specified without a *runner*.
        """

        if not runner:
            if script is not None:
                raise ValueError("cannot specify `script` parameter without a `runner` parameter")
            project_info = self.project_finder.find_project(directory)
            if project_info is not None:
                script, runner = project_info
        if not script and runner:
            script = runner.find_script(directory)

        has_root_project = self._root_project is not None
        project = Project(directory.name, directory, parent, self)
        try:
            if parent:
                parent.add_child(project)

            self.trigger(ContextEvent.Type.on_project_init, project)

            with self.as_current(), project.as_current():
                if not has_root_project:
                    self._root_project = project

                if script is None and require_buildscript:
                    raise ProjectLoaderError(
                        project,
                        f"no buildscript found for {project} (directory: {project.directory.absolute().resolve()})",
                    )
                if script is not None:
                    assert runner is not None
                    runner.execute_script(script, {"project": project})

            self.trigger(ContextEvent.Type.on_project_loaded, project)

        except ProjectLoaderError as exc:
            if exc.project is project:
                # Revert changes if the project that the error occurred with is the current project.
                if not has_root_project:
                    self._root_project = None
                if parent:
                    parent.remove_child(project)
            raise

        return project

    def iter_projects(self, relative_to: Project | None = None) -> Iterator[Project]:
        """Iterates over all projects in the context."""

        def _recurse(project: Project) -> Iterator[Project]:
            yield project
            for child_project in project.subprojects().values():
                yield from _recurse(child_project)

        yield from _recurse(relative_to or self.root_project)

    def get_project(self, address: Address) -> Project:
        """
        Find a project by its address. The address must be absolute.
        """

        if not address.is_absolute():
            raise ValueError(f"address '{address}' is not absolute")

        project: Project | None = self.root_project
        assert project is not None

        for element in address.elements:
            project = project.subproject(element.value, "or-none")
            if not project:
                raise ProjectNotFoundError(address)

        return project

    def resolve_tasks(
        self,
        addresses: Iterable[Task | str | Address] | None,
        relative_to: Project | Address | None = None,
        set_selected: bool = False,
    ) -> list[Task]:
        """
        This method finds Kraken tasks by their address, relative to a given project. If no project is
        specified, the address is resolved relative to the root project.

        :param addresses: A list of task addresses to resolve. Task addresses may contain glob patterns
            (`*` and `**` as well as `?` at the end of an address element, see the #Address class for
            more details).

            Any address that consists of only a single non-globbing path element (such as `lint` or `test`)
            will be prefixed by a wildcard (such that they are semantically equivalent to `**:lint` and
            `**:test`, respectively).

            In case the address specifies a container (that is, if it ends with a colon), then this will
            resolve the default tasks or this container.
            As an example, `:` will get the default tasks of the current project, and `:**:` will get the
            default tasks of all sub-projects.
            Specifying `None` is a shorthand for resolving `:` and `:**:`, that is, will resolve to the
            default tasks of the current project and its sub-projects.

        :param relative_to: The Kraken project to resolve the task addresses relative to. If this is not
            specified, the #root_project is used instead.

        :param set_selected: If enabled, addresses that resolve to tasks immediately will be marked as selected
            before they are returned. Note that this does not mark tasks as selected when they are picked up by
            via the default tasks of a project. For example, when `:*` is resolved, the default tasks of all
            sub-projects will be returned, but they will not be marked as selected. The tasks of the root project
            however, will be marked as selected.
        """

        if not isinstance(relative_to, Address):
            relative_to = relative_to.address if relative_to is not None else Address.ROOT

        if not relative_to.is_absolute():
            raise ValueError(f"'relative_to' must be an absolute address (got {relative_to!r})")

        if addresses is None:
            addresses = [
                ".:",  # The current project (will be "expanded" to its default tasks)
                "**:",  # All sub-projects (will be "expanded" to their default tasks)
            ]

        results: list[Task] = []
        space = KrakenAddressSpace(self.root_project)
        for address in addresses:
            if isinstance(address, Task):
                results.append(address)
                continue
            try:
                results += self._resolve_single_address(Address(address), relative_to, space, set_selected)
            except TaskResolutionException:
                if address == "**:":
                    # In case the project has no sub-projects, it is expected not to find any tasks there
                    pass
                else:
                    raise

        return results

    def _resolve_single_address(
        self,
        address: Address,
        relative_to: Address,
        space: KrakenAddressSpace,
        set_selected: bool,
    ) -> list[Task]:
        """
        Resolve a single address in the context.

        Any address that contains only a single path element (such as `lint` or `test`) will be prefixed
        with `**:`, such that they are semantically equivalent to `**:lint` and `**:test`, respectively.
        """

        if address.is_empty():
            raise TaskResolutionException("Impossible to resolve the empty address.")

        # Prefix single-element addresses with `**:`, unless the last element already is `**`.
        if (
            not address.is_absolute()
            and not address.is_container()
            and len(address) == 1
            and not address.elements[0].is_recursive_wildcard()
        ):
            address = Address.RECURSIVE_WILDCARD.concat(address)
        if not address.is_absolute():
            address = relative_to.concat(address).normalize(keep_container=True)

        matches = list(resolve_address(space, self.root_project, address).matches())
        tasks = [t for t in matches if isinstance(t, Task)]
        if set_selected:
            for task in tasks:
                task.selected = True
        projects = [p for p in matches if isinstance(p, Project)]
        if projects:
            # Using the address of a project means we want to select its default tasks
            for proj in projects:
                tasks += [task for task in proj.tasks().values() if task.default]
        if not tasks:
            raise TaskResolutionException(f"'{address}' refers to no tasks.")
        return tasks

    def finalize(self) -> None:
        """Call :meth:`Task.finalize()` on all tasks. This should be called before a graph is created."""

        if self._finalized:
            logger.warning("Context.finalize() called more than once", stack_info=True)
            return
        self._finalized = True

        with self.as_current():
            self.trigger(ContextEvent.Type.on_context_begin_finalize, self)

            # Delegate to finalize calls in all tasks of all projects.
            for project in self.iter_projects():
                self.trigger(ContextEvent.Type.on_project_begin_finalize, project)
                for task in project.tasks().values():
                    task.finalize()
                self.trigger(ContextEvent.Type.on_project_finalized, project)

            self.trigger(ContextEvent.Type.on_context_finalized, self)

    def get_build_graph(self, targets: Sequence[str | Address | Task] | None) -> TaskGraph:
        """Returns the :class:`TaskGraph` that contains either all default tasks or the tasks specified with
        the *targets* argument.

        :param targets: A list of targets to resolve and to build the graph from.
        :raise ValueError: If not tasks were selected.
        """

        if targets is None:
            tasks = self.resolve_tasks(None)
        else:
            needs_resolving, resolved = bipartition(lambda t: isinstance(t, Task), targets)
            tasks = cast(list[Task], list(resolved))
            tasks.extend(self.resolve_tasks(needs_resolving))

        if not tasks:
            raise ValueError("no tasks selected")

        graph = TaskGraph(self).trim(tasks)

        assert graph, "TaskGraph cannot be empty"
        return graph

    def execute(self, tasks: list[str | Address | Task] | TaskGraph | None = None) -> TaskGraph:
        """Execute all default tasks or the tasks specified by *targets* using the default executor.
        If :meth:`finalize` was not called already it will be called by this function before the build
        graph is created, unless a build graph is passed in the first place.

        :param tasks: The list of tasks to execute, or the build graph. If none specified, all default
            tasks will be executed.
        :raise BuildError: If any task fails to execute.
        """

        if isinstance(tasks, TaskGraph):
            assert self._finalized, "no, no, this is all wrong. you need to finalize the context first"
            graph = tasks
        else:
            if not self._finalized:
                self.finalize()
            graph = self.get_build_graph(tasks)

        self.executor.execute_graph(graph, self.observer)

        if not graph.is_complete():
            raise BuildError(list(graph.tasks(failed=True)))
        return graph

    @overload
    def listen(
        self, event_type: str | ContextEvent.Type
    ) -> Callable[[ContextEvent.T_Listener], ContextEvent.T_Listener]: ...

    @overload
    def listen(self, event_type: str | ContextEvent.Type, listener: ContextEvent.Listener) -> None: ...

    def listen(self, event_type: str | ContextEvent.Type, listener: ContextEvent.Listener | None = None) -> Any:
        """Registers a listener to the context for the given event type."""

        if isinstance(event_type, str):
            event_type = ContextEvent.Type[event_type]

        def register(listener: ContextEvent.T_Listener) -> ContextEvent.T_Listener:
            assert callable(listener), "listener must be callable, got: %r" % listener
            self._listeners[event_type].append(listener)
            return listener

        if listener is None:
            return register

        register(listener)

    def trigger(self, event_type: ContextEvent.Type, data: Any) -> None:
        assert isinstance(event_type, ContextEvent.Type), repr(event_type)
        assert event_type != ContextEvent.Type.any, "cannot trigger event of type 'any'"
        listeners = (*self._listeners.get(ContextEvent.Type.any, ()), *self._listeners.get(event_type, ()))
        for listener in listeners:
            # TODO(NiklasRosenstein): Should we catch errors in listeners of letting them propagate?
            listener(ContextEvent(event_type, data))
