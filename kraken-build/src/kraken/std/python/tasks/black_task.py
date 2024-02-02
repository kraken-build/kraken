from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

from kraken.common import Supplier
from kraken.core import Project, Property
from kraken.core.system.task import TaskStatus
from kraken.std.python.settings import python_settings
from kraken.std.python.tasks.pex_build_task import pex_build

from .base_task import EnvironmentAwareDispatchTask


@dataclass
class BlackConfig:
    line_length: int
    exclude_directories: Sequence[str] = ()

    def dump(self) -> dict[str, Any]:
        config = {}

        # TODO(@niklas): For some reason Black doesn't recognize this option the way we try to pass it.. It definitely
        #       worked in kraken-hs, but I can't tell what's differenet (we write in the same format to a `black.cfg`
        #       file).
        config["line_length"] = str(self.line_length)

        # Apply overrides from the project config.
        if self.exclude_directories:
            exclude_patterns = []
            for dirname in self.exclude_directories or ():
                exclude_patterns.append("^/" + re.escape(dirname.strip("/")) + "/.*$")
            exclude_regex = "(" + "|".join(exclude_patterns) + ")"
            config["exclude"] = exclude_regex

        return config

    def to_file(self, path: Path) -> None:
        path.write_text(tomli_w.dumps(self.dump()))


class BlackTask(EnvironmentAwareDispatchTask):
    """A task to run the `black` formatter to either check for necessary changes or apply changes."""

    python_dependencies = ["black"]

    black_bin: Property[str] = Property.default("black")
    check_only: Property[bool] = Property.default(False)
    config: Property[BlackConfig | None] = Property.default(None)
    config_file: Property[Path | None] = Property.default(None)
    paths: Property[Sequence[str]] = Property.default_factory(list)
    additional_args: Property[Sequence[str]] = Property.default_factory(list)

    __config_file: Path | None = None

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        command = [self.black_bin.get(), *self.paths.get()]
        if self.check_only.get():
            command += ["--check", "--diff"]
        config = self.config.get()
        if config:
            command += ["--line-length", str(config.line_length)]
        if self.__config_file:
            command += ["--config", str(self.__config_file.absolute())]
        command += self.additional_args.get()
        return command

    # Task

    def get_description(self) -> str | None:
        if self.check_only.get():
            return "Check Python source files formatting with Black."
        else:
            return "Format Python source files with Black."

    def prepare(self) -> TaskStatus | None:
        config = self.config.get()
        config_file = self.config_file.get()
        if config is not None and config_file is not None:
            raise RuntimeError("BlackTask.config and .config_file cannot be mixed")
        if config is not None:
            config_file = self.project.build_directory / self.name / "black.cfg"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config.to_file(config_file)
        self.__config_file = config_file
        return super().prepare()


@dataclass
class BlackTasks:
    check: BlackTask
    format: BlackTask


def black(
    *,
    name: str = "python.black",
    project: Project | None = None,
    config: BlackConfig | None = None,
    config_file: Path | Supplier[Path] | None = None,
    additional_args: Sequence[str] | Supplier[Sequence[str]] = (),
    paths: Sequence[str] | Supplier[Sequence[str]] | None = None,
    version_spec: str | None = None,
) -> BlackTasks:
    """Creates two black tasks, one to check and another to format. The check task will be grouped under `"lint"`
    whereas the format task will be grouped under `"fmt"`.

    :param version_spec: If specified, the Black tool will be installed as a PEX and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()

    if version_spec is not None:
        black_bin = pex_build(
            "black",
            requirements=[f"black{version_spec}"],
            console_script="black",
            project=project,
        ).output_file.map(str)
    else:
        black_bin = Supplier.of("black")

    if paths is None:
        paths = python_settings(project).get_source_paths()

    check_task = project.task(f"{name}.check", BlackTask, group="lint")
    check_task.black_bin = black_bin
    check_task.check_only = True
    check_task.config = config
    check_task.config_file = config_file
    check_task.additional_args = additional_args
    check_task.paths = paths

    format_task = project.task(name, BlackTask, group="fmt")
    format_task.black_bin = black_bin
    format_task.check_only = False
    format_task.config = config
    format_task.config_file = config_file
    format_task.additional_args = additional_args
    format_task.paths = paths

    return BlackTasks(check_task, format_task)
