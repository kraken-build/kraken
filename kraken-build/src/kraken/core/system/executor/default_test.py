from collections.abc import Generator

from _pytest.capture import CaptureFixture, CaptureResult
from pytest import raises

from kraken.core.system.executor import GraphExecutorObserver
from kraken.core.system.executor.default import (
    TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE,
    DefaultGraphExecutor,
    DefaultPrintingExecutorObserver,
    DefaultTaskExecutor,
)
from kraken.core.system.graph import TaskGraph
from kraken.core.system.project import Project
from kraken.core.system.task import Task, TaskStatus, VoidTask


class MyTask(Task):
    """
    Fake task
    """

    def execute(self) -> None:
        print("Hello")


class MyFailingTask(Task):
    """
    Fake failing task
    """

    def execute(self) -> None:
        raise RuntimeError("Wow this is failing")


def execute_print_test(graph: TaskGraph) -> None:
    """
    Basic common execution to get the final printed result
    """
    default_task_executor = DefaultTaskExecutor()
    default_printing_executor_observer = DefaultPrintingExecutorObserver()
    default_executor = DefaultGraphExecutor(default_task_executor)
    default_executor.execute_graph(graph, default_printing_executor_observer)


def trim_printed_result(captured: CaptureResult[str]) -> str:
    """
    Retrieving the skipped test printed part
    """
    print_output = str(captured.out)
    title_index_end = print_output.find(TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE) + len(
        TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE
    )
    result = print_output[(title_index_end + 1) :]
    return result


def test__DefaultExecutor__print_correct_failures_with_dependencies(
    kraken_project: Project, capsys: Generator[CaptureFixture[str], None, None]
) -> None:
    """This test tests if when a task failed, successor tasks with dependencies will be printed as failed.

    ```
    A -> B -> C -> D
    ```

    If B fails, C, D should be printed.
    """
    task_a = kraken_project.task("fake_task_a", MyTask)
    task_b = kraken_project.task("fake_task_b", MyFailingTask)
    task_c = kraken_project.task("fake_task_c", MyTask)
    task_d = kraken_project.task("fake_task_d", MyTask)

    task_b.depends_on(task_a)
    task_c.depends_on(task_b)
    task_d.depends_on(task_c)

    graph = TaskGraph(kraken_project.context).trim([task_d])
    assert set(graph.tasks()) == {task_a, task_b, task_c, task_d}
    execute_print_test(graph)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    result = trim_printed_result(captured)
    assert TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE in captured.out
    assert ":fake_task_c" in result
    assert ":fake_task_d" in result


def test__DefaultExecutor__print_correct_failures_inside_groups_without_dependencies(
    kraken_project: Project, capsys: Generator[CaptureFixture[str], None, None]
) -> None:
    """This test tests if when a task failed within a group, the group will not be printed as failed.

    ```
    Group "group", Tasks: A, B, C
    ```

    If B fails, C is not printed as failed.
    """

    kraken_project.task("fake_task_a", MyTask, group="group")
    kraken_project.task("fake_task_b", MyFailingTask, group="group")
    kraken_project.task("fake_task_c", MyTask, group="group")

    group = kraken_project.group("group")

    graph = TaskGraph(kraken_project.context).trim([group])
    execute_print_test(graph)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE not in captured.out
    result = trim_printed_result(captured)
    assert ":group" not in result


def test__DefaultExecutor__print_correct_failures_inside_group_with_dependency(
    kraken_project: Project, capsys: Generator[CaptureFixture[str], None, None]
) -> None:
    """This test tests if when a task failed within a group,
     successor tasks with dependencies will be printed as failed.

    ```
    Group
    A
    |
    v
    B
    | \
    v  v
    C  D
    ```
    If B fails, C and D should be printed as failed
    """
    task_a = kraken_project.task("fake_task_a", MyTask, group="group")
    task_b = kraken_project.task("fake_task_b", MyFailingTask, group="group")
    task_c = kraken_project.task("fake_task_c", MyTask, group="group")
    task_d = kraken_project.task("fake_task_d", MyTask, group="group")

    group = kraken_project.group("group")

    task_b.depends_on(task_a)
    task_c.depends_on(task_b)
    task_d.depends_on(task_b)

    graph = TaskGraph(kraken_project.context).trim([group])
    execute_print_test(graph)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE in captured.out
    result = trim_printed_result(captured)
    assert ":fake_task_c" in result
    assert ":fake_task_d" in result
    assert ":fake_task_b" not in result


def test__DefaultExecutor__print_correct_failures_with_independent_groups(
    kraken_project: Project, capsys: Generator[CaptureFixture[str], None, None]
) -> None:
    """This test tests if when a task failed within one group, a following independent group will not be affected
    ```
    Group 1,  Group 2
    A           D
    |           |
    v           v
    B           E
    |           |
    v           v
    C           F
    ```
    If B fails, C will be printed
    """
    task_a = kraken_project.task("fake_task_a", MyTask, group="g1")
    task_b = kraken_project.task("fake_task_b", MyFailingTask, group="g1")
    task_c = kraken_project.task("fake_task_c", MyTask, group="g1")
    task_d = kraken_project.task("fake_task_d", MyTask, group="g2")
    task_e = kraken_project.task("fake_task_e", MyTask, group="g2")
    task_f = kraken_project.task("fake_task_f", MyTask, group="g2")

    g1 = kraken_project.group("g1")
    g2 = kraken_project.group("g2")

    task_b.depends_on(task_a)
    task_c.depends_on(task_b)
    task_e.depends_on(task_d)
    task_f.depends_on(task_e)

    graph = TaskGraph(kraken_project.context).trim([g1, g2])
    execute_print_test(graph)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE in captured.out
    result = trim_printed_result(captured)
    assert ":fake_task_c" in result
    assert ":fake_task_d" not in result
    assert ":fake_task_e" not in result
    assert ":fake_task_f" not in result


def test__DefaultExecutor__print_correct_failures_with_dependent_groups(
    kraken_project: Project, capsys: Generator[CaptureFixture[str], None, None]
) -> None:
    """This test tests if when a task failed within one group,
     successor tasks with dependencies will be printed as failed.
    If another group has a relationship with the failing group, its tasks will also be printed as failed.
    ```
    Group 1 --> Group 2
    A           D
    |           |
    v           v
    B           E
    |           |
    v           v
    C           F
    ```
    If B fails, C, D, E and F will be printed
    """
    task_a = kraken_project.task("fake_task_a", MyTask, group="g1")
    task_b = kraken_project.task("fake_task_b", MyFailingTask, group="g1")
    task_c = kraken_project.task("fake_task_c", MyTask, group="g1")
    task_d = kraken_project.task("fake_task_d", MyTask, group="g2")
    task_e = kraken_project.task("fake_task_e", MyTask, group="g2")
    task_f = kraken_project.task("fake_task_f", MyTask, group="g2")

    g1 = kraken_project.group("g1")
    g2 = kraken_project.group("g2")

    task_b.depends_on(task_a)
    task_c.depends_on(task_b)
    task_e.depends_on(task_d)
    task_f.depends_on(task_e)

    g2.depends_on(g1)

    graph = TaskGraph(kraken_project.context).trim([g2])
    execute_print_test(graph)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert TASKS_SKIPPED_DUE_TO_FAILING_DEPENDENCIES_TITLE in captured.out
    result = trim_printed_result(captured)
    assert ":fake_task_c" in result
    assert ":fake_task_d" in result
    assert ":fake_task_e" in result
    assert ":fake_task_f" in result


def test__DefaultTaskExecutor__skips_tasks_to_be_skipped(kraken_project: Project) -> None:
    t1 = kraken_project.task("t1", VoidTask)
    t1.add_tag("skip", reason="This task must be skipped.")
    t2 = kraken_project.task("t2", MyTask)

    statuses: list[TaskStatus] = []

    def done(status: TaskStatus) -> None:
        statuses.append(status)

    with raises(RuntimeError) as excinfo:
        DefaultTaskExecutor().execute_task(t1, done)
    assert str(excinfo.value) == f"Tasks that are set to be skipped must not be passed into the task executor: {t1!r}"
    DefaultTaskExecutor().execute_task(t2, done)

    assert statuses == [TaskStatus.succeeded()]


def test__DefaultGraphExecutor__skips_tasks_to_be_skipped(kraken_project: Project) -> None:
    t1 = kraken_project.task("t1", VoidTask)
    t1.add_tag("skip", reason="This task must be skipped.")
    kraken_project.task("t2", MyTask)

    statuses: list[TaskStatus] = []

    class Observer(GraphExecutorObserver):
        def after_execute_task(self, task: Task, status: TaskStatus) -> None:
            statuses.append(status)

    executor = DefaultGraphExecutor(DefaultTaskExecutor())
    executor.execute_graph(TaskGraph(kraken_project.context), Observer())

    assert statuses == [TaskStatus.skipped("This task must be skipped."), TaskStatus.succeeded()]
