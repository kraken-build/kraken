from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent

from pytest import mark, raises

from kraken.core.address import Address, AddressResolutionError
from kraken.core.cli.main import main

from tests.kraken_core.conftest import chdir_context


@contextmanager
def setup_plain_project(directory: Path) -> Iterator[None]:
    """
    Writes Kraken build script into *directory* that creates one task that writes a `root.txt`
    file into *directory*.
    """

    build_script_code = dedent(
        """
        from kraken.core import Project
        from kraken.std.util.render_file_task import render_file

        render_file(name="task", file="root.txt", content="This is in root")
        """
    )
    build_script = directory / ".kraken.py"
    build_script.write_text(build_script_code)
    with chdir_context(directory):
        yield


@contextmanager
def setup_project_with_subproject(directory: Path, chdir_subproject: bool) -> Iterator[None]:
    """
    Writes Kraken build script into *directory* that creates two tasks and a subproject.
    Each task lives in a different project, both are called "task" and they each produce
    a file in the *directory*. The task in the root project produces a `root.txt` file
    while the task in the sub project produces a `sub.txt` file.
    """

    build_script_code = dedent(
        """
        from kraken.core import Project
        from kraken.std.util.render_file_task import render_file

        sub = Project.current().subproject("sub")

        render_file(name="task", file="root.txt", content="This is in root")
        render_file(name="task", file="sub.txt", content="This is in sub", project=sub)
        """
    )
    build_script = directory / ".kraken.py"
    build_script.write_text(build_script_code)
    (directory / "sub").mkdir()
    with chdir_context(directory / "sub" if chdir_subproject else directory):
        yield


@mark.parametrize(argnames=("task_selector",), argvalues=[[":task"], ["task"]])
def test__main__run_in_plain_project(tempdir: Path, task_selector: str) -> None:
    with setup_plain_project(tempdir):
        with raises(SystemExit) as excinfo:
            main(argv=["run", task_selector], handle_exceptions=False)
        assert excinfo.value.code == 0

    # Assert that the file created by the task exists.
    assert (tempdir / "root.txt").is_file()


@mark.parametrize(argnames=("task_selector",), argvalues=[[":task"], ["task"]])
def test__main__run_in_plain_project_from_subdirectory(tempdir: Path, task_selector: str) -> None:
    """
    Verifies that the Kraken CLI can be run from inside a sub-directory that does not contain a Kraken
    script, pointing to the parent project directory and correctly resolve tasks as per the project to a
    directory 1:1 mapping.

        /
            .kraken.py
            sub/            [cwd]
                (empty)

    * Running `:test` from inside `sub/` should find the task in the root project.
    * Running `test` from inside `sub/` should error because `sub/` has no project and thus also no tasks.
    """

    is_absolute = Address(task_selector).is_absolute()
    (tempdir / "sub").mkdir()

    if is_absolute:
        expected_error_type: type[BaseException] = SystemExit
    else:
        expected_error_type = AddressResolutionError

    print("Expected error type:", expected_error_type)

    with setup_plain_project(tempdir), chdir_context(tempdir / "sub"):
        with raises(expected_error_type) as excinfo:
            main(argv=["run", "--project-dir", "..", task_selector], handle_exceptions=False)

    if is_absolute:
        assert isinstance(excinfo.value, SystemExit)
        assert excinfo.value.code == 0
        # Assert that the file created by the task exists.
        assert (tempdir / "root.txt").is_file()
    else:
        assert str(excinfo.value) == (
            "Could not resolve address ':sub:**:task' in context ':'. The failure occurred at address ':' "
            "trying to resolve the remainder 'sub:**:task'. The address ':sub' does not exist."
        )


@mark.parametrize(argnames=("task_selector",), argvalues=[[":task"], ["task"]])
def test__main__run_with_subproject_from_root(tempdir: Path, task_selector: str) -> None:
    with setup_project_with_subproject(tempdir, chdir_subproject=False):
        with raises(SystemExit) as excinfo:
            main(argv=["run", task_selector], handle_exceptions=False)
        assert excinfo.value.code == 0

    # Assert that the files created by the tasks exist.
    if Address(task_selector).is_absolute():
        assert (tempdir / "root.txt").is_file()
        assert not (tempdir / "sub.txt").is_file()
    else:
        assert (tempdir / "root.txt").is_file()
        assert (tempdir / "sub.txt").is_file()


@mark.parametrize(argnames=("task_selector",), argvalues=[[":task"], ["task"]])
def test__main__run_with_subproject_from_subproject(tempdir: Path, task_selector: str) -> None:
    with setup_project_with_subproject(tempdir, chdir_subproject=True):
        with raises(SystemExit) as excinfo:
            main(argv=["run", "--project-dir", "..", task_selector], handle_exceptions=False)
        assert excinfo.value.code == 0

    # Assert that the files created by the tasks exist.
    if Address(task_selector).is_absolute():
        assert (tempdir / "root.txt").is_file()
        assert not (tempdir / "sub.txt").is_file()
    else:
        assert not (tempdir / "root.txt").is_file()
        assert (tempdir / "sub.txt").is_file()
