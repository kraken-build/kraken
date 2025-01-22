from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from pytest import fixture

from kraken.common._buildscript import BuildscriptMetadata
from kraken.common._generic import not_none
from kraken.common._runner import CurrentDirectoryProjectFinder, GitAwareProjectFinder, PythonScriptRunner
from kraken.core import Project


@fixture
def tempdir() -> Iterator[Path]:
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test__PythonScriptRunner__can_find_and_execute_script(tempdir: Path, kraken_project: Project) -> None:
    (tempdir / ".kraken.py").write_text(
        dedent(
            """
        from kraken.common import buildscript

        buildscript(requirements=["kraken-std"])
        """
        )
    )
    runner = PythonScriptRunner()
    script = runner.find_script(tempdir)
    assert script is not None

    with BuildscriptMetadata.capture() as metadata_future:
        runner.execute_script(script, {})

    assert metadata_future.result() == BuildscriptMetadata(requirements=["kraken-std"])


def test__GitAwareProjectFinder__finds_highest_script(tempdir: Path) -> None:
    finder = GitAwareProjectFinder(CurrentDirectoryProjectFinder([PythonScriptRunner()]))

    (tempdir / "foo" / "bar").mkdir(parents=True)
    (tempdir / "foo" / ".kraken.py").write_text("")
    (tempdir / ".kraken.py").write_text("")  # <<< result

    script, _ = not_none(finder.find_project(directory=tempdir / "foo" / "bar"))
    assert script == tempdir / ".kraken.py"


def test__GitAwareProjectFinder__finds_highest_script_but_does_not_cross_home_boundary(tempdir: Path) -> None:
    finder = GitAwareProjectFinder(CurrentDirectoryProjectFinder([PythonScriptRunner()]), home_boundary=tempdir)

    # With the home_boundary set to tempdir, it will not pick scripts in any directory directly inside of tempdir,
    # e.g. tempdir/foo/.kraken.py is off-limits.

    (tempdir / "foo" / "bar").mkdir(parents=True)
    (tempdir / "foo" / "bar" / ".kraken.py").write_text("")  # <<< result
    (tempdir / "foo" / ".kraken.py").write_text("")
    (tempdir / ".kraken.py").write_text("")

    script, _ = not_none(finder.find_project(directory=tempdir / "foo" / "bar"))
    assert script == tempdir / "foo" / "bar" / ".kraken.py"


def test__GitAwareProjectFinder__finds_highest_script_but_does_not_cross_git(tempdir: Path) -> None:
    finder = GitAwareProjectFinder(CurrentDirectoryProjectFinder([PythonScriptRunner()]))

    (tempdir / "foo" / "bar").mkdir(parents=True)
    (tempdir / "foo" / "bar" / ".kraken.py").write_text("")
    (tempdir / "foo" / ".kraken.py").write_text("")  # <<< result
    (tempdir / "foo" / ".git").write_text("")
    (tempdir / ".kraken.py").write_text("")

    script, _ = not_none(finder.find_project(directory=tempdir / "foo" / "bar"))
    assert script == tempdir / "foo" / ".kraken.py"
