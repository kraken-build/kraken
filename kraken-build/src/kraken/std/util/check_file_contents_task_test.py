import os
import unittest.mock

from pytest import CaptureFixture

from kraken.core import Project
from kraken.core.system.task import TaskStatus
from kraken.std.util.check_file_contents_task import CheckFileContentsTask


@unittest.mock.patch.dict(os.environ, {"ANSI_COLORS_DISABLED": "1"})
def test__CheckFileContentsTask__shows_diff(kraken_project: Project, capsys: CaptureFixture[str]) -> None:
    path = kraken_project.directory / "file.txt"
    path.write_text("Hello, world!\n", encoding="utf8")

    task = kraken_project.task("checkFile", CheckFileContentsTask)
    task.file = path
    task.encoding = "utf8"
    task.content = "Hello, world!\nGoodbye, world!\n"
    status = task.execute()
    assert status == TaskStatus.failed(f'file "{path}" is not up to date')

    assert capsys.readouterr().out.splitlines(keepends=True) == [
        "  Hello, world!\n",
        "+ Goodbye, world!\n",
    ]
