import pytest

from kraken.core.system.graph import TaskGraph
from kraken.core.system.project import Project
from kraken.core.system.task import TaskStatus, VoidTask


def test__TaskGraph__populate(kraken_project: Project) -> None:
    task_a = kraken_project.do("a", VoidTask, group="g")
    task_b = kraken_project.do("b", VoidTask, group="g")
    group = kraken_project.group("g")

    graph = TaskGraph(kraken_project.context, False)
    graph.populate([group])

    assert set(graph.tasks()) == {group, task_a, task_b}
    assert set(graph.tasks(goals=True)) == {group}


def test__TaskGraph__trim(kraken_project: Project) -> None:
    task_a = kraken_project.do("a", VoidTask, group="g")
    task_b = kraken_project.do("b", VoidTask, group="g")
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
    task_a = kraken_project.do("a", VoidTask, group="g1")
    task_b = kraken_project.do("b", VoidTask, group="g2")
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

    task_a = kraken_project.do("a", VoidTask)
    task_b = kraken_project.do("b", VoidTask)
    task_c = kraken_project.do("c", VoidTask)

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

    task_a = kraken_project.do("a", VoidTask)
    task_b = kraken_project.do("b", VoidTask)
    task_c = kraken_project.do("c", VoidTask)
    task_d = kraken_project.do("d", VoidTask)

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

    pythonBuild = kraken_project.do("pythonBuild", VoidTask, group="build")
    pythonPublish = kraken_project.do("pythonPublish", VoidTask, group="publish")
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

    python_install = kraken_project.do("pythonInstall", VoidTask)
    jtd_python = kraken_project.do("jtd.python", VoidTask, group="gen")
    gen = kraken_project.group("gen")
    build = kraken_project.group("build")
    pytest = kraken_project.do("pytest", VoidTask)

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
    ta1 = kraken_project.do("ta1", VoidTask, group=a)
    ta2 = kraken_project.do("ta2", VoidTask, group=a)
    tb1 = kraken_project.do("tb1", VoidTask, group=b)

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

    ta1 = kraken_project.do("ta1", VoidTask, group=a)
    ta2 = kraken_project.do("ta2", VoidTask, group=a)
    tb1 = kraken_project.do("tb1", VoidTask, group=b)

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

    ta1 = kraken_project.do("ta1", VoidTask, group=a)
    ta2 = kraken_project.do("ta2", VoidTask, group=a)

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

    ta1 = kraken_project.do("ta1", VoidTask, group=a)
    ta2 = kraken_project.do("ta2", VoidTask, group=a)
    tb1 = kraken_project.do("tb1", VoidTask, group=b)

    b.depends_on(a, mode="order-only")
    graph = TaskGraph(kraken_project.context)
    assert list(graph.ready()) == [ta1, ta2]

    graph.set_status(ta1, TaskStatus.failed())
    assert list(graph.ready()) == [ta2]

    graph.set_status(ta2, TaskStatus.failed())
    assert list(graph.ready()) == [tb1]
