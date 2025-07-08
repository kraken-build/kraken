from __future__ import annotations

import dataclasses
import warnings
from collections.abc import MutableMapping, Sequence
from pathlib import Path

from kraken.common.supplier import Supplier
from kraken.core import Project, Property
from kraken.core.system.task import TaskStatus

from .base_task import EnvironmentAwareDispatchTask


class PyclnTask(EnvironmentAwareDispatchTask):
    """A task to run the `pycln` formatter to either check for necessary changes or apply changes."""

    python_dependencies = ["pycln"]

    pycln_cmd: Property[Sequence[str]] = Property.default(["pycln"])
    check_only: Property[bool] = Property.default(False)
    config_file: Property[Path]
    additional_args: Property[list[str]] = Property.default_factory(list)
    additional_files: Property[list[Path]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        warnings.warn(
            "python.pycln will be removed in a future version. Please use python.ruff instead.",
            DeprecationWarning,
            stacklevel=4,
        )

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str] | TaskStatus:
        command = [*self.pycln_cmd.get(), str(self.settings.source_directory)]
        command += self.settings.get_tests_directory_as_args()
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        command += [str(p) for p in self.additional_files.get()]
        if self.check_only.get():
            command += ["--check", "--diff"]
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get().absolute())]
        command += self.additional_args.get()
        return command

    def get_description(self) -> str:
        if self.check_only.get():
            return "Check Python imports with Pycln."
        else:
            return "Remove unused Python imports with Pycln."


@dataclasses.dataclass
class PyclnTasks:
    check: PyclnTask
    format: PyclnTask


def pycln(*, name: str = "python.pycln", project: Project | None = None, version_spec: str | None = None) -> PyclnTasks:
    """Creates two pycln tasks, one to check and another to format. The check task will be grouped under `"lint"`
    whereas the format task will be grouped under `"fmt"`.

    :param version_spec: If specified, the pycln tool will be run via `uv tool run` and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()
    if version_spec is not None:
        pycln_cmd = Supplier.of(["uv", "tool", "run", "--from", f"pycln{version_spec}", "pycln"])
    else:
        pycln_cmd = Supplier.of(["pycln"])

    check_task = project.task(f"{name}.check", PyclnTask, group="lint")
    check_task.pycln_cmd = pycln_cmd
    check_task.check_only = True
    format_task = project.task(name, PyclnTask, group="fmt")
    format_task.pycln_cmd = pycln_cmd
    return PyclnTasks(check_task, format_task)
