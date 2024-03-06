from __future__ import annotations

import os
from collections.abc import Sequence
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property
from kraken.core.system.task import TaskStatus
from kraken.std.python.settings import python_settings
from kraken.std.python.tasks.pex_build_task import pex_build

from .base_task import EnvironmentAwareDispatchTask


@dataclass
class IsortConfig:
    profile: str
    line_length: int = 80
    combine_as_imports: bool = True
    extend_skip: Sequence[str] = ()

    def to_config(self) -> ConfigParser:
        section_name = "isort"
        config = ConfigParser()
        config.add_section(section_name)
        config.set(section_name, "profile", self.profile)
        config.set(section_name, "line_length", str(self.line_length))
        config.set(section_name, "combine_as_imports", str(self.combine_as_imports).lower())
        config.set(section_name, "extend_skip", ",".join(self.extend_skip))
        return config

    def to_file(self, path: Path) -> None:
        config = self.to_config()
        with path.open("w") as fp:
            config.write(fp)


class IsortTask(EnvironmentAwareDispatchTask):
    python_dependencies = ["isort"]

    isort_bin: Property[str] = Property.default("isort")
    check_only: Property[bool] = Property.default(False)
    config: Property[IsortConfig | None] = Property.default(None)
    config_file: Property[Path | None] = Property.default(None)
    paths: Property[Sequence[str]] = Property.default_factory(list)

    __config_file: Path | None = None

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = [self.isort_bin.get(), *self.paths.get()]
        if self.check_only.get():
            command += ["--check-only", "--diff"]
        if self.__config_file:
            command += ["--settings-file", str(self.__config_file)]

        # When running isort from a PEX binary, we have to point it explicitly at the virtual env
        # and source directories to ensure it knows what imports are first, second and third party.
        if venv := os.getenv("VIRTUAL_ENV"):
            command += ["--virtual-env", venv]
        settings = python_settings(project=self.project)
        for path in filter(None, [settings.source_directory, settings.get_tests_directory()]):
            command += ["--src", str(path)]

        return command

    # Task

    def get_description(self) -> str | None:
        if self.check_only.get():
            return "Check Python source files formatting with isort."
        else:
            return "Format Python source files with isort."

    def prepare(self) -> TaskStatus | None:
        config = self.config.get()
        config_file = self.config_file.get()
        if config is not None and config_file is not None:
            raise RuntimeError("IsortTask.config and .config_file cannot be mixed")
        if config is not None:
            config_file = self.project.build_directory.absolute() / self.name / "isort.ini"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config.to_file(config_file)
        self.__config_file = config_file
        return super().prepare()


@dataclass
class IsortTasks:
    check: IsortTask
    format: IsortTask


def isort(
    *,
    name: str = "python.isort",
    project: Project | None = None,
    config: IsortConfig | None = None,
    config_file: Path | Supplier[Path] | None = None,
    paths: Sequence[str] | Supplier[Sequence[str]] | None = None,
    version_spec: str | None = None,
) -> IsortTasks:
    """
    :param version_spec: If specified, the isort tool will be installed as a PEX and does not need to be installed
        into the Python project's virtual env.
    """

    # TODO (@NiklasRosenstein): We may need to ensure an order to isort and block somehow, sometimes they yield
    #       slightly different results based on the order they run.
    project = project or Project.current()

    if version_spec is not None:
        isort_bin = pex_build(
            "isort",
            requirements=[f"isort{version_spec}"],
            console_script="isort",
            project=project,
        ).output_file.map(str)
    else:
        isort_bin = Supplier.of("isort")

    if paths is None:
        paths = python_settings(project).get_source_paths()

    check_task = project.task(f"{name}.check", IsortTask, group="lint")
    check_task.isort_bin = isort_bin
    check_task.check_only = True
    check_task.config = config
    check_task.config_file = config_file
    check_task.paths = paths

    format_task = project.task(name, IsortTask, group="fmt")
    format_task.isort_bin = isort_bin
    format_task.config = config
    format_task.check_only = False
    format_task.config_file = config_file
    format_task.paths = paths

    # When we run both, it makes no sense to run the check task before the format task.
    check_task.depends_on(format_task, mode="order-only")

    return IsortTasks(check_task, format_task)
