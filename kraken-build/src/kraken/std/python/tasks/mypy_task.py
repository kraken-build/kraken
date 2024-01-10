from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property

from .base_task import EnvironmentAwareDispatchTask


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
        entry_point = "dmypy" if self.use_daemon.get() else "mypy"

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
        if self.use_daemon.get():
            command += ["--status-file", str(status_file), "run", "--"]
        if mypy_pex_bin:
            # Have mypy pick up the Python executable from the virtual environment that is activated automatically
            # during the execution of this task as this is an "EnvironmentAwareDispatchTask". If we don't supply this
            # option, MyPy will only know the packages in it's PEX.
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
) -> MypyTask:
    project = project or Project.current()
    task = project.task(name, MypyTask, group="lint")
    task.config_file = config_file
    task.additional_args = additional_args
    task.check_tests = check_tests
    task.use_daemon = use_daemon
    task.python_version = python_version
    return task
