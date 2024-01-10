import logging
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from kraken.core import Project
from kraken.std.python.tasks.pex_build_task import PexBuildTask


def test__PexBuildTask__install_isort(kraken_project: Project) -> None:
    task = kraken_project.task("isort.install", PexBuildTask)
    task.binary_name = "isort"
    task.console_script = "isort"
    task.requirements = ["isort==5.13.2"]
    kraken_project.context.execute([task])

    # The PEX must exist.
    assert task.output_file.get().is_file()

    # Save the mtime for later (we don't expect the file to be updated on rerun because it already exists).
    mtime = task.output_file.get().stat().st_mtime

    kraken_project.context.execute([task])
    assert task.output_file.get().stat().st_mtime == mtime, "PEX has been rebuilt on subsequent run!"

    # The isort PEX can be run to sort some Python code!
    with TemporaryDirectory() as tmp:
        tmpfile = Path(tmp) / "main.py"
        tmpfile.write_text(
            dedent(
                """
                from kraken.core import Task, Project
                import threading
                from time import time
                from sys import executable
                """
            )
        )
        command = [str(task.output_file.get()), str(tmpfile)]
        logging.info("$ %s", command)
        subprocess.check_call(command)
        assert tmpfile.read_text() == dedent(
            """
            import threading
            from sys import executable
            from time import time

            from kraken.core import Project, Task
            """
        )
