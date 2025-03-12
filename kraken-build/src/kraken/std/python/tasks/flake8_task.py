from __future__ import annotations

import warnings
from collections.abc import MutableMapping, Sequence
from itertools import chain
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property
from kraken.core.system.task import TaskStatus

from .base_task import EnvironmentAwareDispatchTask


class Flake8Task(EnvironmentAwareDispatchTask):
    """
    Lint Python source files with Flake8.
    """

    description = "Lint Python source files with Flake8."
    python_dependencies = ["flake8"]

    flake8_cmd: Property[Sequence[str]] = Property.default(["flake8"])
    config_file: Property[Path]
    additional_args: Property[list[str]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        warnings.warn(
            "python.flake8 will be removed in a future version. Please use python.ruff instead.",
            DeprecationWarning,
            stacklevel=4,
        )

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str] | TaskStatus:
        command = [
            *self.flake8_cmd.get(),
            str(self.settings.source_directory),
        ] + self.settings.get_tests_directory_as_args()
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get().absolute())]
        command += self.additional_args.get()
        return command


def flake8(
    *,
    name: str = "python.flake8",
    project: Project | None = None,
    config_file: Path | Supplier[Path] | None = None,
    version_spec: str | None = None,
    additional_requirements: Sequence[str] = (),
) -> Flake8Task:
    """Creates a task for linting your Python project with Flake8.

    :param version_spec: If specified, the Flake8 tool will be run via `uv tool run` and does not need to be installed
        into the Python project's virtual env.
    :param additional_requirements: Additional requirements to pass to `uv tool run`.
    """

    project = project or Project.current()

    if version_spec is not None:
        flake8_cmd = Supplier.of(
            [
                "uv",
                "tool",
                "run",
                "--from",
                f"flake8{version_spec}",
                *chain.from_iterable(("--with", r) for r in additional_requirements),
                "flake8",
            ]
        )
    else:
        flake8_cmd = Supplier.of(["flake8"])

    task = project.task(name, Flake8Task, group="lint")
    task.flake8_cmd = flake8_cmd
    if config_file is not None:
        task.config_file = config_file
    return task
