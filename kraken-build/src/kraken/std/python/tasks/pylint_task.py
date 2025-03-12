from __future__ import annotations

import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import MutableMapping

from kraken.common import Supplier
from kraken.core import Project, Property
from kraken.core.system.task import TaskStatus

from .base_task import EnvironmentAwareDispatchTask


class PylintTask(EnvironmentAwareDispatchTask):
    description = "Lint Python source files with Pylint"
    python_dependencies = ["pylint"]

    pylint_cmd: Property[Sequence[str]] = Property.default(["pylint"])
    config_file: Property[Path]
    additional_args: Property[Sequence[str]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        warnings.warn(
            "python.pylint will be removed in a future version. Please use python.ruff instead.",
            DeprecationWarning,
            stacklevel=4,
        )

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str] | TaskStatus:
        command = [
            *self.pylint_cmd.get(),
            str(self.settings.source_directory),
        ] + self.settings.get_tests_directory_as_args()
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        if self.config_file.is_filled():
            command += ["--rcfile", str(self.config_file.get())]
        command += self.additional_args.get()
        return command


def pylint(
    *,
    name: str = "python.pylint",
    project: Project | None = None,
    config_file: Path | Supplier[Path] | None = None,
    additional_args: Sequence[str] | Property[Sequence[str]] = (),
    version_spec: str | None = None,
) -> PylintTask:
    """
    :param version_spec: If specified, the pylint tool will be run via `uv tool run` and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()
    if version_spec is not None:
        pylint_cmd = Supplier.of(["uv", "tool", "run", "--from", f"pylint{version_spec}", "pylint"])
    else:
        pylint_cmd = Supplier.of(["pylint"])

    task = project.task(name, PylintTask, group="lint")
    task.pylint_cmd = pylint_cmd
    task.config_file = config_file
    task.additional_args = additional_args
    return task
