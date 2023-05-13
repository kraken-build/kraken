import subprocess
from pathlib import Path

from kraken.core.api import Project

from kraken.std.util.check_file_exists_and_is_committed_task import (
    CheckFileExistsAndIsCommittedError,
    CheckFileExistsAndIsCommittedTask,
)
from tests.conftest import chdir_context


def test__file_does_not_exist(kraken_project: Project) -> None:
    file_path = kraken_project.directory / "warbl.garbl"
    test_task = kraken_project.do(
        "test__file_does_not_exist", CheckFileExistsAndIsCommittedTask, group="check", file_to_check=file_path
    )

    assert test_task._check() == CheckFileExistsAndIsCommittedError.DOES_NOT_EXIST
    assert test_task.execute().is_failed()


def test__file_exists_but_is_not_committed(kraken_project: Project, tempdir: Path) -> None:
    with chdir_context(tempdir):
        subprocess.run(["git", "init"])
        subprocess.run(["git", "commit", "-am", '"Initial commit"'])

        file_name = Path("warbl.garbl")
        file_name.touch()

    kraken_project.directory = tempdir
    test_task = kraken_project.do(
        "test__file_exists_but_is_not_committed",
        CheckFileExistsAndIsCommittedTask,
        group="check",
        file_to_check=file_name,
    )

    assert test_task._check() == CheckFileExistsAndIsCommittedError.IS_NOT_COMMITTED
    assert test_task.execute().is_failed()


def test__file_exists_and_is_committed(kraken_project: Project) -> None:
    # kraken_project.directory is ROOT / src / tests / util --> .parent x3 results in ROOT
    file_path = kraken_project.directory.parent.parent.parent / ".kraken.py"
    test_task = kraken_project.do(
        "test__file_exists_and_is_committed", CheckFileExistsAndIsCommittedTask, group="check", file_to_check=file_path
    )

    assert test_task._check() is None
    assert test_task.execute().is_succeeded()
