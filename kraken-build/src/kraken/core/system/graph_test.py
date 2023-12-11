import logging
from typing import Any

import pytest

from kraken.core.system.graph import TaskGraph
from kraken.core.system.project import Project
from kraken.core.system.task import GroupTask, TaskStatus, VoidTask


def test__TaskGraph__populate(kraken_project: Project) -> None:
    task_a = kraken_project.task("a", VoidTask, group="g")
    task_b = kraken_project.task("b", VoidTask, group="g")
    group = kraken_project.group("g")

    graph = TaskGraph(kraken_project.context, False)
    graph.populate([group])

    assert set(graph.tasks()) == {group, task_a, task_b}
    assert set(graph.tasks(goals=True)) == {group}


def test__TaskGraph__trim(kraken_project: Project) -> None:
    task_a = kraken_project.task("a", VoidTask, group="g")
    task_b = kraken_project.task("b", VoidTask, group="g")
    group = kraken_project.group("g")

    graph = TaskGraph(kraken_project.context).trim([group])

    assert set(graph.tasks()) == {group, task_a, task_b}
    assert set(graph.tasks(goals=True)) == {group}

    # Trimming should have the same result as a fresh populate.
    fresh_graph = TaskGraph(kraken_project.context, populate=False)
    fresh_graph.populate([group])
    assert fresh_graph._digraph.nodes == graph._digraph.nodes
    assert fresh_graph._digraph.edges == graph._digraph.edges


def test__TaskGraph__trim_with_nested_groups(kraken_project: Project) -> None:
    task_a = kraken_project.task("a", VoidTask, group="g1")
    task_b = kraken_project.task("b", VoidTask, group="g2")
    group_1 = kraken_project.group("g1")
    group_2 = kraken_project.group("g2")
    group_1.add(group_2)

    graph = TaskGraph(kraken_project.context).trim([group_1, group_2])

    assert set(graph.tasks()) == {group_2, group_1, task_a, task_b}
    assert set(graph.tasks(goals=True)) == {group_1}

    # Trimming should have the same result as a fresh populate.
    fresh_graph = TaskGraph(kraken_project.context, populate=False)
    fresh_graph.populate([group_1])
    assert fresh_graph._digraph.nodes == graph._digraph.nodes
    assert fresh_graph._digraph.edges == graph._digraph.edges


def test__TaskGraph__ready_on_successful_completion(kraken_project: Project) -> None:
    """Tests if :meth:`TaskGraph.ready` and :meth:`TaskGraph.is_complete` work as expected.

    ```
    A -----> B -----> C
    ```
    """

    task_a = kraken_project.task("a", VoidTask)
    task_b = kraken_project.task("b", VoidTask)
    task_c = kraken_project.task("c", VoidTask)

    task_c.depends_on(task_b)
    task_b.depends_on(task_a)

    graph = TaskGraph(kraken_project.context).trim([task_c])

    assert set(graph.tasks()) == {task_c, task_b, task_a}
    assert list(graph.execution_order()) == [task_a, task_b, task_c]

    # Complete tasks one by one.
    remainder = [task_a, task_b, task_c]
    while remainder:
        assert list(graph.execution_order()) == remainder
        task = remainder.pop(0)
        assert not graph.is_complete()
        assert list(graph.ready()) == [task]
        graph.set_status(task, TaskStatus.succeeded())

    assert graph.is_complete()
    assert list(graph.ready()) == []


def test__TaskGraph__ready_on_failure(kraken_project: Project) -> None:
    """This test tests if the task delivers the correct ready tasks if a task in the graph fails.

    ```
    A        B
    |        |
    v        v
    C -----> D
    ```

    If A succeeds but B fails, C would still be executable, but D stays dormant.
    """

    task_a = kraken_project.task("a", VoidTask)
    task_b = kraken_project.task("b", VoidTask)
    task_c = kraken_project.task("c", VoidTask)
    task_d = kraken_project.task("d", VoidTask)

    task_d.depends_on(task_b)
    task_d.depends_on(task_c)
    task_c.depends_on(task_a)

    graph = TaskGraph(kraken_project.context).trim([task_d])
    assert set(graph.tasks()) == {task_d, task_b, task_c, task_a}
    assert list(graph.execution_order()) in ([task_a, task_b, task_c, task_d], [task_b, task_a, task_c, task_d])
    assert set(graph.ready()) == {task_a, task_b}

    # After B fails we can still run A.
    graph.set_status(task_b, TaskStatus.failed())
    assert list(graph.ready()) == [task_a]

    # After A is successful we can still run C.
    graph.set_status(task_a, TaskStatus.succeeded())
    assert list(graph.ready()) == [task_c]

    # D cannot continue because B has failed.
    graph.set_status(task_c, TaskStatus.succeeded())
    assert list(graph.ready()) == []
    assert not graph.is_complete()


def test__TaskGraph__ready_2(kraken_project: Project) -> None:
    """
    ```
    pythonBuild -----> pythonPublish -----> publish (group)
     \\-----> build (group)
    ```
    """

    pythonBuild = kraken_project.task("pythonBuild", VoidTask, group="build")
    pythonPublish = kraken_project.task("pythonPublish", VoidTask, group="publish")
    pythonPublish.depends_on(pythonBuild)

    publish = kraken_project.group("publish")
    graph = TaskGraph(kraken_project.context).trim([publish])
    assert list(graph.ready()) == [pythonBuild]


def test__TaskGraph__correct_execution_order_on_optional_intermediate_task(kraken_project: Project) -> None:
    """Test that the TaskGraph produces the correct order in a scenario where two tasks that need to be
    executed have another that does not need to be executed in between.

    ```
    pythonInstall --------------------------> pytest
    \\---> jtd.python ===> gen ---> (X) build - - ->/
    ```

    The expected order here is that the `pytest` task can only run after `gen`. It is important to note that
    the `pytest` task only depends optionally on the `build` task, otherwise of course running `pytest` would
    require that `build` is executed as well.

    Legend:

    * `- ->`: optional dependency
    * `--->`: strict dependency
    * `===>`: member of group
    """

    python_install = kraken_project.task("pythonInstall", VoidTask)
    jtd_python = kraken_project.task("jtd.python", VoidTask, group="gen")
    gen = kraken_project.group("gen")
    build = kraken_project.group("build")
    pytest = kraken_project.task("pytest", VoidTask)

    pytest.depends_on(python_install)
    pytest.depends_on(build, mode="order-only")
    build.depends_on(gen)
    jtd_python.depends_on(python_install)

    graph = TaskGraph(kraken_project.context)

    assert list(graph.trim([pytest, gen]).execution_order()) == [python_install, jtd_python, gen, pytest]

    assert list(graph.trim([pytest, build]).execution_order()) == [python_install, jtd_python, gen, build, pytest]


@pytest.mark.parametrize("inverse", [False, True])
def test__TaskGraph__test_inverse_group_relationship(kraken_project: Project, inverse: bool) -> None:
    """Tests that the dependency propagation between members of task groups works as expected.

    Consider two groups A and B. When B depends on A, the task graph automatically expands that dependency
    to the members of B such that each depend on the members of A. This fact is stored on the edge using
    the "implicit" marker (i.e. the relationship between the tasks was not explicit using direct task
    relationships).

    :param inverse: Whether the relationship between the groups should be expressed using an inverse relationship.
        `A -> B` should yield the same result as `B <- A`.
    """

    from kraken.core.system.graph import _Edge

    a = kraken_project.group("a")
    b = kraken_project.group("b")
    ta1 = kraken_project.task("ta1", VoidTask, group=a)
    ta2 = kraken_project.task("ta2", VoidTask, group=a)
    tb1 = kraken_project.task("tb1", VoidTask, group=b)

    if inverse:
        a.required_by(b)
    else:
        b.depends_on(a)

    graph = TaskGraph(kraken_project.context)
    assert graph.get_edge(ta1, a) == _Edge(True, False)
    assert graph.get_edge(ta2, a) == _Edge(True, False)
    assert graph.get_edge(tb1, b) == _Edge(True, False)
    assert graph.get_edge(a, b) == _Edge(True, False)

    # Implicit propagated edges.
    assert graph.get_edge(a, tb1) == _Edge(True, True)

    assert list(graph.trim([b]).execution_order()) == [ta1, ta2, a, tb1, b]


def test__TaskGraph__allow_subsequent_group_execution_on_non_strict_failed_tasks(kraken_project: Project) -> None:
    """Tests that the TaskGraph correctly allows the graph execution to continue if non-strict dependencies fail, but
    correctly returns that the graph is not complete.

    Consider two groups A and B, where B depends on A but not strictly. A should be executed before B, but if any
    tasks in A fail the TaskGraph should still allow B to be executed afterwards as the dependency is not strict. The
    TaskGraph however should not consider the graph to be `complete` after B finishes executing as there still is a
    failed task.
    """
    a = kraken_project.group("a")
    b = kraken_project.group("b")

    ta1 = kraken_project.task("ta1", VoidTask, group=a)
    ta2 = kraken_project.task("ta2", VoidTask, group=a)
    tb1 = kraken_project.task("tb1", VoidTask, group=b)

    b.depends_on(a, mode="order-only")
    graph = TaskGraph(kraken_project.context)
    assert list(graph.ready()) == [ta1, ta2]

    graph.set_status(ta1, TaskStatus.succeeded())
    graph.set_status(ta2, TaskStatus.failed())

    assert list(graph.ready()) == [tb1]

    graph.set_status(tb1, TaskStatus.succeeded())
    assert not graph.is_complete()


def test__TaskGraph__allow_subsequent_task_execution_on_non_strict_failed_tasks(kraken_project: Project) -> None:
    """Tests that the TaskGraph correctly allows the graph execution to continue if non-strict dependencies fail, but
    correctly returns that the graph is not complete.

    Consider two tasks within the same group, A1 and A2. A1 should be executed before A2, but if A1 fails the TaskGraph
    should still allow A2 to be executed afterwards as the dependency is not strict. The TaskGraph however should not
    consider the graph to be `complete` after A2 finishes executing as there still is a failed task.
    """
    a = kraken_project.group("a")

    ta1 = kraken_project.task("ta1", VoidTask, group=a)
    ta2 = kraken_project.task("ta2", VoidTask, group=a)

    ta2.depends_on(ta1, mode="order-only")
    graph = TaskGraph(kraken_project.context)
    assert list(graph.ready()) == [ta1]

    graph.set_status(ta1, TaskStatus.failed())

    assert list(graph.ready()) == [ta2]

    graph.set_status(ta2, TaskStatus.succeeded())
    assert not graph.is_complete()


def test__TaskGraph__wait_for_group_finish_before_removing_non_strict_dependencies(kraken_project: Project) -> None:
    """Tests that the TaskGraph correctly waits for all tasks within a group to succeed or fail, before removing
    any non-strict dependencies to allow subsequent tasks to execute.
    """
    a = kraken_project.group("a")
    b = kraken_project.group("b")

    ta1 = kraken_project.task("ta1", VoidTask, group=a)
    ta2 = kraken_project.task("ta2", VoidTask, group=a)
    tb1 = kraken_project.task("tb1", VoidTask, group=b)

    b.depends_on(a, mode="order-only")
    graph = TaskGraph(kraken_project.context)
    assert list(graph.ready()) == [ta1, ta2]

    graph.set_status(ta1, TaskStatus.failed())
    assert list(graph.ready()) == [ta2]

    graph.set_status(ta2, TaskStatus.failed())
    assert list(graph.ready()) == [tb1]


def test__TaskGraph__mark_tasks_as_skipped__does_not_skip_task_required_by_another_unskipped_task(
    kraken_project: Project, caplog: Any
) -> None:
    """This test verifies that recursively marking tasks as skipped will not mark tasks that are still required by
    other tasks that are not skipped."""

    # Set up a graph like this:
    #
    # a <-- b
    # ^__   ^
    #    \  |
    #     - c
    #
    # When we recursively mark "b" as skipped recursively, we expect that "c" is not marked as skipped because
    # "a" still requires it.

    a = kraken_project.task("a", VoidTask)
    b = kraken_project.task("b", VoidTask)
    c = kraken_project.task("c", VoidTask)

    a.depends_on(b, c)
    b.depends_on(c)

    graph = TaskGraph(kraken_project.context)
    graph.mark_tasks_as_skipped(recursive_tasks=[b], reason="test", origin="test", reset=True)

    assert [t.name for t in a.get_tags("skip")] == []
    assert [t.name for t in b.get_tags("skip")] == ["skip"]
    assert [t.name for t in c.get_tags("skip")] == []


def test__TaskGraph__mark_tasks_as_skipped__does_skip_task_if_requierd_by_another_skipped_task(
    kraken_project: Project, caplog: Any
) -> None:
    """This test builds a TaskGraph that would have the `mark_tasks_as_skipped()` method pass through a recursively
    discovered task that depends on another such task, and both should be excluded. The test verifies that both are
    excluded correctly, rather than the first discovered is not excluded because it has not been passed yet and thus
    not marked as skipped (so still seeming like it requires the first task)."""

    # Set up a graph like this:
    #
    # a <-- b
    # ^__   ^
    #    \  |
    #     - c
    #
    # When we recursively mark "a" as skipped, we expect both "b" and "c" to be skipped as well.

    a = kraken_project.task("a", VoidTask)
    b = kraken_project.task("b", VoidTask)
    c = kraken_project.task("c", VoidTask)

    a.depends_on(b, c)
    b.depends_on(c)

    graph = TaskGraph(kraken_project.context)
    with caplog.at_level(logging.DEBUG):
        graph.mark_tasks_as_skipped(recursive_tasks=[a], reason="test", origin="test", reset=True)

    assert [t.name for t in a.get_tags("skip")] == ["skip"]
    assert [t.name for t in b.get_tags("skip")] == ["skip"]
    assert [t.name for t in c.get_tags("skip")] == ["skip"]


def test__TaskGraph__mark_tasks_as_skipped__keep_transitive_required_dependencies_unmarked(
    kraken_project: Project,
) -> None:
    r"""
    Another scenario for ensuring the correctness of #TaskGraph.mark_tasks_as_skipped().

    ```
    pyproject.check -> python.test.integration -> python.test
                   \            ^                 ^
                    \          /                 /
                     v        /                 /
    python.login -> python.install -> python.test.unit

    # Not displayed here: pyproject.check -> python.test.unit
    ```

    Selecting `python.test` but excluding the subgraph of `python.test.integration` should only exclude that task,
    because all other tasks are still required by `python.test.unit`.
    """

    pyproject_check = kraken_project.task("pyproject.check", VoidTask)
    python_login = kraken_project.task("python.login", VoidTask)
    python_install = kraken_project.task("python.install", VoidTask)
    python_test_integration = kraken_project.task("python.test.integration", VoidTask)
    python_test_unit = kraken_project.task("python.test.unit", VoidTask)
    python_test = kraken_project.task("python.test", VoidTask)

    python_test.depends_on(python_test_integration, python_test)
    python_test_integration.depends_on(pyproject_check, python_install)
    python_test_unit.depends_on(pyproject_check, python_install)
    python_install.depends_on(pyproject_check, python_login)

    graph = TaskGraph(kraken_project.context)
    graph.mark_tasks_as_skipped(recursive_tasks=[python_test_integration], reason="test", origin="test", reset=True)

    skipped_tasks = []
    for task in graph.tasks():
        if isinstance(task, GroupTask):
            continue
        if [t.name for t in task.get_tags("skip")] == ["skip"]:
            skipped_tasks.append(str(task.address))

    assert skipped_tasks == [":python.test.integration"]
