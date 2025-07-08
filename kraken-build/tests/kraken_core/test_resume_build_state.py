import logging
from contextlib import ExitStack
from pathlib import Path
from textwrap import dedent

from pytest import mark

from kraken.common import not_none, safe_rmpath
from kraken.core.address import Address
from kraken.core.cli.executor import ColoredDefaultPrintingExecutorObserver
from kraken.core.cli.main import _load_build_state
from kraken.core.cli.option_sets import BuildOptions, GraphOptions
from kraken.core.system.task import Task, TaskStatus, TaskStatusType

from tests.kraken_core.conftest import chdir_context

logger = logging.getLogger(__name__)


class RecordingExecutorObserver(ColoredDefaultPrintingExecutorObserver):
    def __init__(self) -> None:
        super().__init__()
        self.executed_tasks: list[Address] = []

    def after_execute_task(self, task: Task, status: TaskStatus) -> None:
        self.executed_tasks.append(task.address)
        return super().after_execute_task(task, status)


@mark.integration
def test_resume_build_state(tempdir: Path) -> None:
    """
    Tests if the build resumption works as expected.

    * Creates a project with three tasks, "a", "b" and "c" where "c" depends on "a" and "b"
    * Executes the tasks individually, resuming the build state after task "a"
    * Observes that only the individual task is run each time
        * In particular, when task "c" is run it should not also run task "a" and "b" because according
          to the build state they have already been run.
    """

    # Set up a test build directory and script.
    build_script = tempdir / ".kraken.py"
    build_script_code = dedent(
        """
        from kraken.std.util.render_file_task import render_file
        from kraken.core import Project

        project = Project.current()

        render_file(name="a", file=project.build_directory / "a.txt", content="This is file a.txt")
        render_file(name="b", file=project.build_directory / "b.txt", content="This is file b.txt")
        render_file(name="c", file=project.build_directory / "c.txt", content="This is file b.txt")

        project.task("c").depends_on("a")
        project.task("c").depends_on("b")
        """
    )
    build_script.write_text(build_script_code)

    build_options = BuildOptions(
        build_dir=tempdir / "build",
        project_dir=tempdir,
        state_dir=tempdir / ".state",
        additional_state_dirs=[],
        no_load_project=False,
        state_name="state-a",
    )

    logger.info('Executing task "a"')
    with ExitStack() as exit_stack, chdir_context(tempdir):
        graph_options = GraphOptions(["a"], resume=False, restart=False, no_save=False, all=False)
        context, graph = _load_build_state(exit_stack, build_options, graph_options)

        # Should only execute task "a".
        observer = RecordingExecutorObserver()
        context.executor.execute_graph(graph, observer)

        assert observer.executed_tasks == [Address(":a")]

        assert not_none(graph.get_status(graph.get_task(":a"))).type == TaskStatusType.SUCCEEDED
        assert graph.get_status(graph.get_task(":b")) is None
        assert graph.get_status(graph.get_task(":c")) is None

        assert (build_options.build_dir / "a.txt").is_file()

    logger.info('Executing task "b"')
    with ExitStack() as exit_stack, chdir_context(tempdir):
        graph_options = GraphOptions(["b"], resume=True, restart=False, no_save=False, all=False)
        context, graph = _load_build_state(exit_stack, build_options, graph_options)

        assert not_none(graph.get_status(graph.get_task(":a"))).type == TaskStatusType.SUCCEEDED
        assert graph.get_status(graph.get_task(":b")) is None
        assert graph.get_status(graph.get_task(":c")) is None

        # Should only execute task "b", but task "a" status should be SUCCEEDED from before.
        observer = RecordingExecutorObserver()
        context.executor.execute_graph(graph, observer)

        assert observer.executed_tasks == [Address(":b")]

        assert not_none(graph.get_status(graph.get_task(":a"))).type == TaskStatusType.SUCCEEDED
        assert not_none(graph.get_status(graph.get_task(":b"))).type == TaskStatusType.SUCCEEDED
        assert graph.get_status(graph.get_task(":c")) is None

    logger.info('Executing task "c"')
    with ExitStack() as exit_stack, chdir_context(tempdir):
        graph_options = GraphOptions(["c"], resume=True, restart=False, no_save=False, all=False)
        context, graph = _load_build_state(exit_stack, build_options, graph_options)

        assert list(graph.tasks()) == [graph.get_task(":a"), graph.get_task(":b"), graph.get_task(":c")]
        assert graph._ok_tasks == {Address(":a"), Address(":b")}
        assert not graph.is_complete()
        assert graph.ready() == [graph.get_task(":c")]
        assert not_none(graph.get_status(graph.get_task(":a"))).type == TaskStatusType.SUCCEEDED
        assert not_none(graph.get_status(graph.get_task(":b"))).type == TaskStatusType.SUCCEEDED
        assert graph.get_status(graph.get_task(":c")) is None

        # Should only execute task "b", but task "a" status should be SUCCEEDED from before.
        observer = RecordingExecutorObserver()
        context.executor.execute_graph(graph, observer)

        assert observer.executed_tasks == [Address(":c")]

        assert not_none(graph.get_status(graph.get_task(":a"))).type == TaskStatusType.SUCCEEDED
        assert not_none(graph.get_status(graph.get_task(":b"))).type == TaskStatusType.SUCCEEDED
        assert not_none(graph.get_status(graph.get_task(":c"))).type == TaskStatusType.SUCCEEDED

    logger.info('Confirm that executing task "c" without prior state would execute "a" and "b" as well')
    safe_rmpath(build_options.build_dir)
    with ExitStack() as exit_stack, chdir_context(tempdir):
        graph_options = GraphOptions(["c"], resume=False, restart=False, no_save=False, all=False)
        context, graph = _load_build_state(exit_stack, build_options, graph_options)

        # Should only execute task "b", but task "a" status should be SUCCEEDED from before.
        observer = RecordingExecutorObserver()
        context.executor.execute_graph(graph, observer)

        assert observer.executed_tasks == [Address(":a"), Address(":b"), Address(":c")]

        assert not_none(graph.get_status(graph.get_task(":a"))).type == TaskStatusType.SUCCEEDED
        assert not_none(graph.get_status(graph.get_task(":b"))).type == TaskStatusType.SUCCEEDED
        assert not_none(graph.get_status(graph.get_task(":c"))).type == TaskStatusType.SUCCEEDED
