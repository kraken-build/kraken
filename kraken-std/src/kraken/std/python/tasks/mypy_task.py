from __future__ import annotations

from pathlib import Path
from typing import Any, List

from kraken.core.api import Project, Property

from .base_task import EnvironmentAwareDispatchTask


class MypyTask(EnvironmentAwareDispatchTask):
    description = "Static type checking for Python code using Mypy."
    python_dependencies = ["mypy"]

    config_file: Property[Path]
    additional_args: Property[List[str]] = Property.config(default_factory=list)
    check_tests: Property[bool] = Property.config(default=True)
    use_daemon: Property[bool] = Property.config(default=True)
    python_version: Property[str]

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        # TODO (@NiklasRosenstein): Should we somewhere add a task that ensures `.dmypy.json` is in `.gitignore`?
        #       Having it in the project directory makes it easier to just stop the daemon if it malfunctions (which
        #       happens regularly but is hard to detect automatically).
        status_file = (self.project.directory / ".dmypy.json").absolute()
        command = ["dmypy", "--status-file", str(status_file), "run", "--"] if self.use_daemon.get() else ["mypy"]
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
        command += self.additional_args.get()
        return command


def mypy(*, name: str = "python.mypy", project: Project | None = None, **kwargs: Any) -> MypyTask:
    project = project or Project.current()
    return project.do(name, MypyTask, group="lint", **kwargs)
