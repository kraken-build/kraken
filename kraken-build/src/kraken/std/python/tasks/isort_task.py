from __future__ import annotations

import dataclasses
import warnings
from collections.abc import MutableMapping, Sequence
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property
from kraken.core.system.task import TaskStatus

from .base_task import EnvironmentAwareDispatchTask


class IsortTask(EnvironmentAwareDispatchTask):
    python_dependencies = ["isort"]

    isort_cmd: Property[Sequence[str]] = Property.default(["isort"])
    check_only: Property[bool] = Property.default(False)
    config_file: Property[Path]
    additional_files: Property[Sequence[Path]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        warnings.warn(
            "python.isort will be removed in a future version. Please use python.ruff instead.",
            DeprecationWarning,
            stacklevel=4,
        )

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str] | TaskStatus:
        command = [
            *self.isort_cmd.get(),
            str(self.settings.source_directory),
        ] + self.settings.get_tests_directory_as_args()
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        command += [str(p) for p in self.additional_files.get()]
        if self.check_only.get():
            command += ["--check-only", "--diff"]
        if self.config_file.is_filled():
            command += ["--settings-file", str(self.config_file.get().absolute())]
        return command

    # Task

    def get_description(self) -> str | None:
        if self.check_only.get():
            return "Check Python source files formatting with isort."
        else:
            return "Format Python source files with isort."


@dataclasses.dataclass
class IsortTasks:
    check: IsortTask
    format: IsortTask


def isort(
    *,
    name: str = "python.isort",
    project: Project | None = None,
    config_file: Path | Supplier[Path] | None = None,
    additional_files: Sequence[Path] | Supplier[Sequence[Path]] = (),
    version_spec: str | None = None,
) -> IsortTasks:
    """
    :param version_spec: If specified, the isort tool will be run via `uv tool run` and does not need to be installed
        into the Python project's virtual env.
    """

    # TODO (@NiklasRosenstein): We may need to ensure an order to isort and block somehow, sometimes they yield
    #       slightly different results based on the order they run.
    project = project or Project.current()

    if version_spec is not None:
        isort_cmd = Supplier.of(["uv", "tool", "run", "--from", f"isort{version_spec}", "isort"])
    else:
        isort_cmd = Supplier.of(["isort"])

    check_task = project.task(f"{name}.check", IsortTask, group="lint")
    check_task.isort_cmd = isort_cmd
    check_task.check_only = True
    check_task.config_file = config_file
    check_task.additional_files = additional_files

    format_task = project.task(name, IsortTask, group="fmt")
    format_task.isort_cmd = isort_cmd
    format_task.check_only = False
    format_task.config_file = config_file
    format_task.additional_files = additional_files

    return IsortTasks(check_task, format_task)
