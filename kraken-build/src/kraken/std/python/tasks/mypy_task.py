from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping, Sequence
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property
from kraken.std.python.tasks.pex_build_task import pex_build

from .base_task import EnvironmentAwareDispatchTask

logger = logging.getLogger(__name__)


class MypyTask(EnvironmentAwareDispatchTask):
    description = "Static type checking for Python code using Mypy."
    python_dependencies = ["mypy"]

    mypy_pex_bin: Property[Path | None] = Property.default(None)
    config_file: Property[Path]
    additional_args: Property[Sequence[str]] = Property.default_factory(list)
    check_tests: Property[bool] = Property.default(True)
    use_daemon: Property[bool] = Property.default(True)
    python_version: Property[str]

    # EnvironmentAwareDispatchTask

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str]:
        use_daemon = self.use_daemon.get()
        if use_daemon and sys.platform.startswith("win32"):
            use_daemon = False
            logger.warning("Disable use of mypy daemon due to error in exit code on Windows")

        entry_point = "dmypy" if use_daemon else "mypy"

        if mypy_pex_bin := self.mypy_pex_bin.get():
            # See https://pex.readthedocs.io/en/latest/api/vars.html
            env["PEX_SCRIPT"] = entry_point
            command = [str(mypy_pex_bin)]
        else:
            command = [entry_point]

        # TODO (@NiklasRosenstein): Should we add a task somewhere that ensures `.dmypy.json` is in `.gitignore`?
        #       Having it in the project directory makes it easier to just stop the daemon if it malfunctions (which
        #       happens regularly but is hard to detect automatically).

        status_file = (self.project.directory / ".dmypy.json").absolute()
        if use_daemon:
            command += ["--status-file", str(status_file), "run", "--"]
        if mypy_pex_bin:
            # Have mypy pick up the Python executable from the virtual environment that is activated automatically
            # during the execution of this task as this is an "EnvironmentAwareDispatchTask". If we don't supply this
            # option, MyPy will only know the packages in its PEX.
            command += ["--python-executable", "python"]
        if self.config_file.is_filled():
            command += ["--config-file", str(self.config_file.get().absolute())]
        else:
            command += ["--show-error-codes", "--namespace-packages"]  # Sane defaults. 🙏
        if self.python_version.is_filled():
            command += ["--python-version", self.python_version.get()]
        source_dir = self.settings.source_directory
        command += [str(source_dir)]
        if self.check_tests.get():
            # We only want to add the tests directory if it is not already in the source directory. Otherwise
            # Mypy will find the test files twice and error.
            tests_dir = self.settings.get_tests_directory()
            if tests_dir:
                try:
                    tests_dir.relative_to(source_dir)
                except ValueError:
                    command += [str(tests_dir)]
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        command += self.additional_args.get()
        return command


def mypy(
    *,
    name: str = "python.mypy",
    project: Project | None = None,
    config_file: Path | Supplier[Path] | None = None,
    additional_args: Sequence[str] | Supplier[Sequence[str]] = (),
    check_tests: bool = True,
    use_daemon: bool = True,
    python_version: str | Supplier[str] | None = None,
    version_spec: str | None = None,
) -> MypyTask:
    """
    :param version_spec: If specified, the Mypy tool will be installed as a PEX and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()

    if version_spec is not None:
        mypy_pex_bin = pex_build(
            "mypy", requirements=[f"mypy{version_spec}"], console_script="mypy", project=project
        ).output_file
    else:
        mypy_pex_bin = None

    task = project.task(name, MypyTask, group="lint")
    task.mypy_pex_bin = mypy_pex_bin
    task.config_file = config_file
    task.additional_args = additional_args
    task.check_tests = check_tests
    task.use_daemon = use_daemon
    task.python_version = python_version
    return task
