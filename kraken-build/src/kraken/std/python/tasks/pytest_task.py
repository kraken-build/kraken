from __future__ import annotations

import enum
import os
import shlex
from collections.abc import Sequence
from pathlib import Path

from kraken.common import flatten
from kraken.core import Project, Property, TaskStatus
from kraken.std.python.settings import python_settings

from .base_task import EnvironmentAwareDispatchTask


class CoverageFormat(enum.Enum):
    XML = ("xml", ".xml")
    HTML = ("html", "_html")
    JSON = ("json", ".json")
    LCOV = ("lcov", ".info")
    ANNOTATE = ("annotate", "_annotate")

    def get_format(self) -> str:
        return self.value[0]

    def get_suffix(self) -> str:
        return self.value[1]


class PytestTask(EnvironmentAwareDispatchTask):
    description = "Run unit tests using Pytest."
    python_dependencies = ["pytest"]

    paths: Property[Sequence[str]]
    ignore_dirs: Property[Sequence[Path]] = Property.default_factory(list)
    allow_no_tests: Property[bool] = Property.default(False)
    doctest_modules: Property[bool] = Property.default(True)
    marker: Property[str]
    coverage: Property[CoverageFormat]

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str] | TaskStatus:
        command = ["pytest", "-vv", *self.paths.get()]
        command += flatten(
            ["--ignore", str(self.project.directory / path)]
            for path in self.ignore_dirs.get()
        )
        command += ["--log-cli-level", "INFO"]
        if self.coverage.is_filled():
            coverage_file = f"coverage{self.coverage.get().get_suffix()}"
            command += [
                "--cov-report",
                f"{self.coverage.get().get_format()}:{str(self.project.build_directory / coverage_file)}",
                "--cov-report",
                "term",
                f"--cov={str(self.project.directory / self.settings.source_directory)}",
            ]
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


def pytest(
    *,
    name: str = "pytest",
    group: str = "test",
    project: Project | None = None,
    paths: Sequence[str] | None = None,
    include_dirs: Sequence[str] = (),
    ignore_dirs: Sequence[Path | str] = (),
    allow_no_tests: bool = False,
    doctest_modules: bool = True,
    marker: str | None = None,
    coverage: CoverageFormat | None = None,
) -> PytestTask:
    """Create a task for running Pytest. Note that Pytest must be installed in the Python virtual environment.

    Args:
        paths: The paths that contain Pythen test files. If not specified, uses the test and source directories
            from the project's `PythonSettings`.
    """

    if paths is None:
        paths = python_settings(project).get_source_paths()

    project = project or Project.current()
    task = project.task(name, PytestTask, group=group)
    task.paths = [*paths, *include_dirs]
    task.ignore_dirs = list(map(Path, ignore_dirs))
    task.allow_no_tests = allow_no_tests
    task.doctest_modules = doctest_modules
    task.marker = marker
    task.coverage = coverage
    return task
