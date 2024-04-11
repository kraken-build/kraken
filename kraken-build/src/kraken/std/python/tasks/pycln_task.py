from __future__ import annotations

import dataclasses
from pathlib import Path

from kraken.common.supplier import Supplier
from kraken.core import Project, Property
from kraken.std.python.tasks.pex_build_task import pex_build

from .base_task import EnvironmentAwareDispatchTask


class PyclnTask(EnvironmentAwareDispatchTask):
    """A task to run the `pycln` formatter to either check for necessary changes or apply changes."""

    python_dependencies = ["pycln"]

    pycln_bin: Property[str] = Property.default("pycln")
    check_only: Property[bool] = Property.default(False)
    config_file: Property[Path]
    additional_args: Property[list[str]] = Property.default_factory(list)
    additional_files: Property[list[Path]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = [self.pycln_bin.get(), str(self.settings.source_directory)]
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

    :param version_spec: If specified, the pycln tool will be installed as a PEX and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()
    if version_spec is not None:
        pycln_bin = pex_build(
            "pycln", requirements=[f"pycln{version_spec}"], console_script="pycln", project=project
        ).output_file.map(str)
    else:
        pycln_bin = Supplier.of("pycln")

    check_task = project.task(f"{name}.check", PyclnTask, group="lint")
    check_task.pycln_bin = pycln_bin
    check_task.check_only = True
    format_task = project.task(name, PyclnTask, group="fmt")
    format_task.pycln_bin = pycln_bin
    return PyclnTasks(check_task, format_task)
