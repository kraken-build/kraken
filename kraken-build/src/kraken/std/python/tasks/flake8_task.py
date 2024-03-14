from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property
from kraken.std.python.tasks.pex_build_task import pex_build

from .base_task import EnvironmentAwareDispatchTask


class Flake8Task(EnvironmentAwareDispatchTask):
    """
    Lint Python source files with Flake8.
    """

    description = "Lint Python source files with Flake8."
    python_dependencies = ["flake8"]

    flake8_bin: Property[str] = Property.default("flake8")
    config_file: Property[Path]
    additional_args: Property[list[str]] = Property.default_factory(list)

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = [
            self.flake8_bin.get(),
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

    :param version_spec: If specified, the Flake8 tool will be installed as a PEX and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()

    if version_spec is not None:
        flake8_bin = pex_build(
            "flake8",
            requirements=[f"flake8{version_spec}", *additional_requirements],
            console_script="flake8",
            project=project,
        ).output_file.map(str)
    else:
        flake8_bin = Supplier.of("flake8")

    task = project.task(name, Flake8Task, group="lint")
    task.flake8_bin = flake8_bin
    if config_file is not None:
        task.config_file = config_file
    return task
