from __future__ import annotations

import dataclasses
import logging
from collections.abc import Collection, Iterable, Iterator, Sequence
from typing import TYPE_CHECKING, TypeVar, cast

from networkx import DiGraph, restricted_view, transitive_reduction
from networkx.algorithms import topological_sort

from kraken.common import not_none
from kraken.common.iter import bipartition
from kraken.core.address import Address
from kraken.core.system.executor import Graph
from kraken.core.system.task import GroupTask, Task, TaskStatus, TaskTag

if TYPE_CHECKING:
    from kraken.core.system.context import Context

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _Edge:
    strict: bool
    implicit: bool


class TaskGraph(Graph):
    """The task graph represents a Kraken context's tasks as a directed acyclic graph data structure.

    Before a task graph is passed to an executor, it is usually trimmed to contain only the tasks that are
    needed for the successful and complete execution of the desired set of "goal tasks"."""

    def __init__(self, context: Context, populate: bool = True, parent: TaskGraph | None = None) -> None:
        """Create a new build graph from the given task list.

        :param context: The context that the graph belongs to.
        :param populate: If enabled, the task graph will be immediately populated with the tasks in the context.
            The graph can also be later populated with the :meth:`populate` method.
        """

        self._parent = parent
        self._context = context

        # Nodes have the form {'data': _Node} and edges have the form {'data': _Edge}.
        # NOTE: DiGraph is not runtime-subscriptable.
        self._digraph: DiGraph[Address] = DiGraph()

        # Keep track of task execution results.
        self._results: dict[Address, TaskStatus] = {}

        # All tasks that have a successful or skipped status are stored here.
        self._ok_tasks: set[Address] = set()

        # All tasks that have a failed status are stored here.
        self._failed_tasks: set[Address] = set()

        # Keep track of the tasks that returned TaskStatus.STARTED. That means the task is a background task, and
        # if the TaskGraph is deserialized from a state file to continue the build, background tasks need to be
        # reset so they start again if another task requires them.
        self._background_tasks: set[Address] = set()

        if populate:
            self.populate()

    def __bool__(self) -> bool:
        return len(self._digraph.nodes) > 0

    def __len__(self) -> int:
        return len(self._digraph.nodes)

    # Low level internal API

    def _get_task(self, addr: Address) -> Task | None:
        assert isinstance(addr, Address), type(addr)
        data = self._digraph.nodes.get(addr)
        if data is None:
            return None
        try:
            return cast(Task, data["data"])
        except KeyError:
            raise RuntimeError(f"An unexpected error occurred when fetching the task by address {addr!r}.")

    def _add_task(self, task: Task) -> None:
        self._digraph.add_node(task.address, data=task)
        for rel in task.get_relationships():
            if rel.other_task.address not in self._digraph.nodes:
                self._add_task(rel.other_task)
            a, b = (task, rel.other_task) if rel.inverse else (rel.other_task, task)
            self._add_edge(a.address, b.address, rel.strict, False)

            # If this relationship is one implied through group membership, we're done.
            if isinstance(task, GroupTask) and not rel.inverse and rel.other_task in task.tasks:
                continue

            # When a group depends on some other task, we implicitly make each member of that downstream group
            # depend on the upstream task. If we find another group, we unpack the group further.
            upstream, downstream = (task, rel.other_task) if rel.inverse else (rel.other_task, task)
            if isinstance(downstream, GroupTask):
                downstream_tasks = list(downstream.tasks)
                while downstream_tasks:
                    member = downstream_tasks.pop(0)
                    if member.address not in self._digraph.nodes:
                        self._add_task(member)
                    if isinstance(member, GroupTask):
                        downstream_tasks += member.tasks
                        continue

                    # NOTE(niklas.rosenstein): When a group is nested in another group, we would end up declaring
                    #       that the group depends on itself. That's obviously not supposed to happen. :)
                    if upstream != member:
                        self._add_edge(upstream.address, member.address, rel.strict, True)

    def _get_edge(self, task_a: Address, task_b: Address) -> _Edge | None:
        data = self._digraph.edges.get((task_a, task_b)) or self._digraph.edges.get((task_a, task_b))
        if data is None:
            return None
        return cast(_Edge, data["data"])

    def _add_edge(self, task_a: Address, task_b: Address, strict: bool, implicit: bool) -> None:
        # add_edge() would implicitly add a node, we only want to do that once the node actually exists in
        # the graph though.
        assert task_a in self._digraph.nodes, f"{task_a!r} not yet in the graph"
        assert task_b in self._digraph.nodes, f"{task_b!r} not yet in the graph"
        edge = self._get_edge(task_a, task_b) or _Edge(strict, implicit)
        edge.strict = edge.strict or strict
        edge.implicit = edge.implicit and implicit
        self._digraph.add_edge(task_a, task_b, data=edge)

    # High level internal API

    def _get_required_tasks(self, goals: Iterable[Task]) -> set[Address]:
        """Internal. Return the set of tasks that are required transitively from the goal tasks."""

        def _is_empty_group_subtree(addr: Address) -> bool:
            """
            Returns `True` if the task pointed to by *addr* is a GroupTask and it is empty or only depends on
            other empty groups.
            """

            def _is_empty_group(addr: Address) -> bool:
                """Returns `True` if the task pointed to by *addr* is a GroupTask and it is empty."""

                task = self._get_task(addr)
                if not isinstance(task, GroupTask):
                    return False
                return len(task.tasks) == 0

            def _is_empty_group_or_subtree(addr: Address) -> bool:
                """Returns `True` if the task pointed to by *addr* is a GroupTask and it is empty or only depends
                on other empty groups."""

                task = self._get_task(addr)
                if not isinstance(task, GroupTask):
                    return False
                for pred in self._digraph.predecessors(addr):
                    if not _is_empty_group_or_subtree(pred):
                        return False
                return True

            return _is_empty_group(addr) or _is_empty_group_or_subtree(addr)

        def _recurse_task(addr: Address, visited: set[Address], path: list[Address]) -> None:
            if addr in path:
                raise RuntimeError(f"encountered a dependency cycle: {' → '.join(map(str, path))}")
            visited.add(addr)
            for pred in self._digraph.predecessors(addr):
                if self.get_edge(pred, addr).strict:
                    # If the thing we want to pick up is a GroupTask and it doesn't have any members or other
                    # dependencies that are not also empty groups, we can skip it. It really doesn't need to be in the
                    # build graph.
                    if isinstance(self._get_task(pred), GroupTask):
                        # Check if the group is empty or only depends on other empty groups.
                        if _is_empty_group_subtree(pred):
                            continue
                    _recurse_task(pred, visited, path + [addr])

        active_tasks: set[Address] = set()
        for task in goals:
            _recurse_task(task.address, active_tasks, [])

        return active_tasks

    def _remove_nodes_keep_transitive_edges(self, nodes: Iterable[Address]) -> None:
        """Internal. Remove nodes from the graph, but ensure that transitive dependencies are kept in tact."""

        for addr in nodes:
            for in_task_path in self._digraph.predecessors(addr):
                in_edge = self.get_edge(in_task_path, addr)
                for out_task_path in self._digraph.successors(addr):
                    out_edge = self.get_edge(addr, out_task_path)
                    self._add_edge(
                        in_task_path,
                        out_task_path,
                        strict=in_edge.strict or out_edge.strict,
                        implicit=in_edge.implicit and out_edge.implicit,
                    )
            self._digraph.remove_node(addr)

    def _get_ready_graph(self) -> DiGraph[Address]:
        """Updates the ready graph. Remove all ok tasks (successful or skipped) and any non-strict dependencies
        (edges) on failed tasks."""

        removable_edges: set[tuple[Address, Address]] = set()

        def set_non_strict_edge_for_removal(u: Address, v: Address) -> None:
            out_edge = self.get_edge(u, v)
            if not out_edge.strict:
                removable_edges.add((u, v))

        for failed_task_path in self._failed_tasks:
            for out_task_path in self._digraph.successors(failed_task_path):
                out_task = self._digraph.nodes[out_task_path]["data"]

                if isinstance(out_task, GroupTask):
                    # If the successor is a group task, check that the all of the groups tasks are either successful
                    # or failed, and then remove any non strict dependency (edge) on said group task.
                    group_task_paths = {task.address for task in out_task.tasks}
                    if not group_task_paths.issubset(self._failed_tasks | self._ok_tasks):
                        continue

                    for group_successor_path in self._digraph.successors(out_task_path):
                        set_non_strict_edge_for_removal(out_task_path, group_successor_path)
                else:
                    set_non_strict_edge_for_removal(failed_task_path, out_task_path)

        return cast("DiGraph[Address]", restricted_view(self._digraph, self._ok_tasks, removable_edges))  # type: ignore[no-untyped-call]

    # Public API

    @property
    def context(self) -> Context:
        return self._context

    @property
    def parent(self) -> TaskGraph | None:
        return self._parent

    @property
    def root(self) -> TaskGraph:
        if self._parent:
            return self._parent.root
        return self

    def get_edge(self, pred: Task | Address, succ: Task | Address) -> _Edge:
        if isinstance(pred, Task):
            pred = pred.address
        if isinstance(succ, Task):
            succ = succ.address
        return not_none(self._get_edge(pred, succ), f"edge does not exist ({pred} --> {succ})")

    def get_predecessors(self, task: Task, ignore_groups: bool = False) -> list[Task]:
        """Returns the predecessors of the task in the original full build graph."""

        result = []
        for task in (self.get_task(addr) for addr in self._digraph.predecessors(task.address)):
            if ignore_groups and isinstance(task, GroupTask):
                result += task.tasks
            else:
                result.append(task)
        return result

    def get_status(self, task: Task) -> TaskStatus | None:
        """Return the status of a task."""

        return self._results.get(task.address)

    def populate(self, goals: Iterable[Task] | None = None) -> None:
        """Populate the graph with the tasks from the context. This need only be called if the graph was
        not initially populated in the constructor.

        !!! warning "Inverse relationships"

            This does not recognize inverse relationships from tasks that are not part of *goals* or
            any of their relationships. It is therefore recommended to populate the graph with all tasks in the
            context and use #trim() to reduce the graph.
        """

        if goals is None:
            for project in self.context.iter_projects():
                for task in project.tasks().values():
                    if task.address not in self._digraph.nodes:
                        self._add_task(task)
        else:
            for task in goals:
                if task.address not in self._digraph.nodes:
                    self._add_task(task)

    def trim(self, goals: Sequence[Task]) -> TaskGraph:
        """Returns a copy of the graph that is trimmed to execute only *goals* and their strict dependencies."""

        graph = TaskGraph(self.context, parent=self)
        unrequired_tasks = set(graph._digraph.nodes) - graph._get_required_tasks(goals)
        graph._remove_nodes_keep_transitive_edges(unrequired_tasks)
        graph.results_from(self)
        return graph

    def reduce(self, keep_explicit: bool = False) -> TaskGraph:
        """Return a copy of the task graph that has been transitively reduced.

        :param keep_explicit: Keep non-implicit edges in tact."""

        digraph = self._digraph
        reduced_graph = transitive_reduction(digraph)
        reduced_graph.add_nodes_from(digraph.nodes(data=True))
        reduced_graph.add_edges_from(
            (u, v, digraph.edges[u, v])
            for u, v in digraph.edges
            if (keep_explicit and not digraph.edges[u, v]["data"].implicit) or (u, v) in reduced_graph.edges
        )

        graph = TaskGraph(self.context, populate=False, parent=self)
        graph._digraph = reduced_graph
        graph.results_from(self)

        return graph

    def results_from(self, other: TaskGraph) -> None:
        """Merge the results from the *other* graph into this graph. Only takes the results of tasks that are
        known to the graph. If the same task has a result in both graphs, and one task result is not successful,
        the not successful result is preferred."""

        self._results = {**other._results, **self._results}
        self._ok_tasks.update(other._ok_tasks)
        self._failed_tasks.update(other._failed_tasks)

        for task in self.tasks():
            status_a = self._results.get(task.address)
            status_b = other._results.get(task.address)
            if status_a is not None and status_b is not None and status_a.type != status_b.type:
                resolved_status: TaskStatus | None = status_a if status_a.is_not_ok() else status_b
            else:
                resolved_status = status_a or status_b
            if resolved_status is not None:
                # NOTE: This will already take care of updating :attr:`_background_tasks`.
                self.set_status(task, resolved_status, _force=True)

    def resume(self) -> None:
        """Reset the result of all background tasks that are required by any pending tasks. This needs to be
        called when a build graph is resumed in a secondary execution to ensure that background tasks are active
        for the tasks that require them."""

        reset_tasks: set[Address] = set()
        for task in self.tasks(pending=True):
            for pred in self.get_predecessors(task, ignore_groups=True):
                if pred.address in self._background_tasks:
                    self._background_tasks.discard(pred.address)
                    self._ok_tasks.discard(pred.address)
                    self._failed_tasks.discard(pred.address)
                    self._results.pop(pred.address, None)
                    reset_tasks.add(pred.address)

        if reset_tasks:
            logger.info(
                "Reset the status of %d background task(s): %s", len(reset_tasks), " ".join(map(str, reset_tasks))
            )

    def restart(self) -> None:
        """Discard the results of all tasks."""

        self._results.clear()
        self._ok_tasks.clear()
        self._background_tasks.clear()
        self._failed_tasks.clear()

    def tasks(
        self,
        goals: bool = False,
        pending: bool = False,
        failed: bool = False,
        not_executed: bool = False,
    ) -> Iterator[Task]:
        """Returns the tasks in the graph in arbitrary order.

        :param goals: Return only goal tasks (i.e. leaf nodes).
        :param pending: Return only pending tasks.
        :param failed: Return only failed tasks.
        :param not_executed: Return only not executed tasks (i.e. downstream of failed tasks)"""

        tasks = (self.get_task(addr) for addr in self._digraph)
        if goals:
            # HACK: Cast because of https://github.com/python/typeshed/pull/12472
            tasks = (t for t in tasks if cast(int, self._digraph.out_degree(t.address)) == 0)
        if pending:
            tasks = (t for t in tasks if t.address not in self._results)
        if failed:
            tasks = (t for t in tasks if t.address in self._results and self._results[t.address].is_failed())
        if not_executed:
            tasks = (
                t
                for t in tasks
                if (
                    (t.address not in self._results)
                    or (t.address in self._results and self._results[t.address].is_pending())
                )
            )
        return tasks

    def execution_order(self, all: bool = False) -> Iterable[Task]:
        """Returns all tasks in the order they need to be executed.

        :param all: Return the execution order of all tasks, not just from the target subgraph."""

        order = topological_sort(self._digraph if all else self._get_ready_graph())
        return (self.get_task(addr) for addr in order)

    def mark_tasks_as_skipped(
        self,
        tasks: Sequence[Task | str | Address] = (),
        recursive_tasks: Sequence[Task | str | Address] = (),
        *,
        set_status: bool = False,
        reason: str,
        origin: str,
        reset: bool,
    ) -> None:
        """
        This method adds the `"skip"` tag to all *tasks* and *recursive_tasks*. For the dependencies of the
        *recursive_tasks*, the tag will only be added if the task in question is not required by another task
        that is not being skipped.

        :param set_status: Whether to set #TaskStatusType.SKIPPED for tasks in the graph using #set_status().
        :param reason: A reason to attach to the `"skip"` tag.
        :param origin: An origin to attach to the `"skip"` tag.
        :param reset: Enable this to remove the `"skip"` tags of the same *origin* are removed from all mentioned
            tasks (including transitive dependencies for *recursive_tasks*) the graph first. Note that this does not
            unset any pre-existing task statuses.
        """

        tasks = self.context.resolve_tasks(tasks)
        recursive_tasks = self.context.resolve_tasks(recursive_tasks)

        def get_skip_tag(task: Task) -> TaskTag | None:
            """Return the skip tag associated with this mark operation (i.e., "skip" tags of the same origin)."""

            return next((t for t in task.get_tags("skip") if t.origin == origin), None)

        def iter_predecessors(tasks: Iterable[Task], blackout: Collection[Task]) -> Iterable[Task]:
            """
            Iterate over the predecessors of the given tasks. Skip yielding and recursive iterating over tasks in
            *blackout*.
            """

            stack = list(tasks)
            while stack:
                task = stack.pop()
                if task not in blackout:
                    yield task
                    stack.extend(self.get_predecessors(task))

        # This algorithm works in multiple phases:
        #
        # (1) We gather all tasks that are definitely skipped and mark them with the color "red". We are certain
        #     that these tasks must be skipped because they are either already marked so in the graph, or they are
        #     tasks mentioned directly in the arguments to this function call.
        #
        # (2) We mark the subgraphs (i.e. predecessors) of all recursive_tasks with the color "blue". These are tasks
        #     that can potentially be skipped as well, but we are not sure yet.
        #
        # (3) We walk back through the entire task graph from its leaves, discoloring any "blue" task that we encounter.
        #     If we encounter a "red" task, we keep it colored and ignore its subgraph.

        red_tasks = {*tasks, *recursive_tasks}

        # Add any already skipped tasks to the red tasks, unless reset=True.
        for task in self.tasks():
            if (tag := get_skip_tag(task)) is not None:
                if reset:
                    task.remove_tag(tag)
                else:
                    red_tasks.add(task)

        # Mark predecessors of the recursive_tasks in blue.
        blue_tasks: set[Task] = set()
        for task in iter_predecessors(recursive_tasks, blue_tasks):
            blue_tasks.add(task)

        # Discolor any blue tasks from the root, ignoring any red tasks.
        for task in iter_predecessors(self.tasks(goals=True), red_tasks):
            blue_tasks.discard(task)

        for task in blue_tasks:
            task.add_tag("skip", reason=reason, origin=origin)
            if set_status and self.get_status(task) is None:
                self.set_status(task, TaskStatus.skipped(reason))

    # Graph

    def ready(self) -> list[Task]:
        """Returns all tasks that are ready to be executed. This can be used to constantly query the graph for new
        available tasks as the status of tasks in the graph is updated with :meth:`set_status`. An empty list is
        returned if no tasks are ready. At this point, if no tasks are currently running, :meth:`is_complete` can be
        used to check if the entire task graph was executed successfully."""

        ready_graph = self._get_ready_graph()
        root_set = (
            # HACK: Cast because of https://github.com/python/typeshed/pull/12472
            node
            for node in ready_graph.nodes
            if cast(int, ready_graph.in_degree(node)) == 0 and node not in self._results
        )
        tasks = [self.get_task(addr) for addr in root_set]
        if not tasks:
            return []

        # NOTE(NiklasRosenstein): We don't need to return GroupTasks, we can mark them as skipped right away.
        #       In a future version of Kraken, we want to represent groups not as task objects, so this special
        #       handling code will be obsolete.
        result, groups = map(lambda x: list(x), bipartition((lambda t: isinstance(t, GroupTask)), tasks))
        for group in groups:
            self.set_status(group, TaskStatus.skipped())
        if not result:
            result = self.ready()
        return result

    def get_successors(self, task: Task, ignore_groups: bool = True) -> list[Task]:
        """Returns the successors of the task in the original full build graph.

        Never returns group tasks."""

        result = []
        for task in (self.get_task(addr) for addr in self._digraph.successors(task.address)):
            if ignore_groups and isinstance(task, GroupTask):
                result += task.tasks
            else:
                result.append(task)
        return result

    def get_task(self, addr: Address | str) -> Task:
        if isinstance(addr, str):
            addr = Address(addr)
        if self._parent is None:
            return not_none(self._get_task(addr), lambda: f"no task for {addr!r}")
        return self.root.get_task(addr)

    def set_status(self, task: Task, status: TaskStatus, *, _force: bool = False) -> None:
        """Sets the status of a task, marking it as executed."""

        if not _force and (task.address in self._results and not self._results[task.address].is_started()):
            raise RuntimeError(f"already have a status for task `{task.address}`")
        self._results[task.address] = status
        if status.is_started():
            self._background_tasks.add(task.address)
        if status.is_ok():
            self._ok_tasks.add(task.address)
        if status.is_failed():
            self._failed_tasks.add(task.address)

    def is_complete(self) -> bool:
        """Returns `True` if, an only if, all tasks in the target subgraph have a non-failure result."""

        return set(self._digraph.nodes).issubset(self._ok_tasks)
