from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, List

from kraken.common import flatten
from kraken.core.api import Project, Property, TaskStatus

from .base_task import EnvironmentAwareDispatchTask

# TODO (@NiklasRosenstein): Pytest coverage support


class PytestTask(EnvironmentAwareDispatchTask):
    description = "Run unit tests using Pytest."
    python_dependencies = ["pytest"]

    tests_dir: Property[Path]
    ignore_dirs: Property[List[Path]] = Property.config(default_factory=list)
    allow_no_tests: Property[bool] = Property.config(default=False)
    doctest_modules: Property[bool] = Property.config(default=True)
    marker: Property[str]

    # EnvironmentAwareDispatchTask

    def is_skippable(self) -> bool:
        return self.allow_no_tests.get() and self.tests_dir.is_empty() and not self.settings.get_tests_directory()

    def get_execute_command(self) -> list[str] | TaskStatus:
        tests_dir = self.tests_dir.get_or(None)
        tests_dir = tests_dir or self.settings.get_tests_directory()
        if not tests_dir:
            print("error: no test directory configured and none could be detected")
            return TaskStatus.failed("no test directory configured and none could be detected")
        command = [
            "pytest",
            "-vv",
            str(self.project.directory / self.settings.source_directory),
            str(self.project.directory / tests_dir),
        ]
        command += flatten(["--ignore", str(self.project.directory / path)] for path in self.ignore_dirs.get())
        command += ["--log-cli-level", "INFO"]
        if self.marker.is_filled():
            command += ["-m", self.marker.get()]
        if self.doctest_modules.get():
            command += ["--doctest-modules"]
        command += shlex.split(os.getenv("PYTEST_FLAGS", ""))
        return command

    def handle_exit_code(self, code: int) -> TaskStatus:
        if code == 5 and self.allow_no_tests.get():
            # Pytest returns exit code 5 if no tests were run.
            return TaskStatus.succeeded()
        return TaskStatus.from_exit_code(None, code)


def pytest(*, name: str = "pytest", group: str = "test", project: Project | None = None, **kwargs: Any) -> PytestTask:
    project = project or Project.current()
    return project.do(name, PytestTask, group=group, **kwargs)
