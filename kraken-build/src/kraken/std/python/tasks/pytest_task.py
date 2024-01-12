from __future__ import annotations

import enum
import os
import shlex
from collections.abc import Sequence
from pathlib import Path

from kraken.common import flatten
from kraken.core import Project, Property, TaskStatus

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

    tests_dir: Property[Path]
    include_dirs: Property[Sequence[Path]] = Property.default(())
    ignore_dirs: Property[Sequence[Path]] = Property.default_factory(list)
    allow_no_tests: Property[bool] = Property.default(False)
    doctest_modules: Property[bool] = Property.default(True)
    marker: Property[str]
    coverage: Property[CoverageFormat]

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
            *[str(self.project.directory / path) for path in self.include_dirs.get()],
        ]
        command += flatten(["--ignore", str(self.project.directory / path)] for path in self.ignore_dirs.get())
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
    tests_dir: Path | str | None = None,
    include_dirs: Sequence[Path | str] = (),
    ignore_dirs: Sequence[Path | str] = (),
    allow_no_tests: bool = False,
    doctest_modules: bool = True,
    marker: str | None = None,
    coverage: CoverageFormat | None = None,
) -> PytestTask:
    project = project or Project.current()
    task = project.task(name, PytestTask, group=group)
    task.tests_dir = Path(tests_dir) if tests_dir is not None else None
    task.include_dirs = list(map(Path, include_dirs))
    task.ignore_dirs = list(map(Path, ignore_dirs))
    task.allow_no_tests = allow_no_tests
    task.doctest_modules = doctest_modules
    task.marker = marker
    task.coverage = coverage
    return task
