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
class Flake8Config:
    extend_ignore: Sequence[str]
    exclude: Sequence[str]

    def dump(self, project_root: Path, config_file_dir: Path) -> ConfigParser:
        """Dump to a `ConfigParser` object.

        Args:
            project_root: The root of the Python project from which Flake8 will be run.
            config_file_dir: The directory that will contain the config file. This needs to be specified
                because exclude patterns need to be relative to the configuration file.
        """

        flake8_section = "flake8"

        # Compute the exclude patterns, which need to be relative to the config file.
        exclude = [os.path.relpath(project_root / x, config_file_dir.absolute()) for x in self.exclude]
        # If we find just a '.' or '*', we need to adjust it due to https://github.com/PyCQA/flake8/issues/298
        exclude = ["./*" if x == "." else "./*" if x == "*" else x for x in exclude]

        config = ConfigParser()
        config.add_section(flake8_section)
        config.set(flake8_section, "extend-ignore", ",".join(self.extend_ignore))
        config.set(flake8_section, "exclude", ",".join(exclude))

        # config.add_section(LOCAL_PLUGINS_SECTION)
        # for key, value in local_plugins_config.items():
        #     config.set(LOCAL_PLUGINS_SECTION, key, value)

        return config

    def to_file(self, project_root: Path, config_file: Path) -> None:
        config = self.dump(project_root, config_file.parent)
        with config_file.open("w") as fp:
            config.write(fp)


class Flake8Task(EnvironmentAwareDispatchTask):
    """
    Lint Python source files with Flake8.
    """

    description = "Lint Python source files with Flake8."
    python_dependencies = ["flake8"]

    flake8_bin: Property[str] = Property.default("flake8")
    config: Property[Flake8Config | None] = Property.default(None)
    config_file: Property[Path | None] = Property.default(None)
    paths: Property[Sequence[str]] = Property.default_factory(list)
    additional_args: Property[Sequence[str]] = Property.default_factory(list)

    __config_file: Path | None = None

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = [
            self.flake8_bin.get(),
            *self.paths.get(),
            *self.additional_args.get(),
        ]
        if self.__config_file:
            command += ["--config", str(self.__config_file.absolute())]
        command += self.additional_args.get()
        return command

    # Task

    def prepare(self) -> TaskStatus | None:
        config = self.config.get()
        config_file = self.config_file.get()
        if config is not None and config_file is not None:
            raise RuntimeError("Flake8Task.config and .config_file cannot be mixed")
        if config is not None:
            config_file = self.project.build_directory / self.name / ".flake8"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config.to_file(self.project.directory, config_file)
        self.__config_file = config_file
        return super().prepare()


def flake8(
    *,
    name: str = "python.flake8",
    project: Project | None = None,
    config: Flake8Config | None = None,
    config_file: Path | Supplier[Path] | None = None,
    paths: Sequence[str] | None = None,
    additional_args: Sequence[str] = (),
    version_spec: str | None = None,
    additional_requirements: Sequence[str] = (),
) -> Flake8Task:
    """Creates a task for linting your Python project with Flake8.

    Args:
        paths: A list of paths to pass to Flake8. If not specified, defaults to the source and test directories from
            the project's `PythonSettings`.
        version_spec: If specified, the Flake8 tool will be installed as a PEX and does not need to be installed
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

    if paths is None:
        paths = python_settings(project).get_source_paths()

    task = project.task(name, Flake8Task, group="lint")
    task.flake8_bin = flake8_bin
    task.config = config
    task.config_file = config_file
    task.paths = paths
    task.additional_args = additional_args
    return task
