from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping, Sequence
from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property
from kraken.core.system.task import TaskStatus
from kraken.std.python.settings import python_settings
from kraken.std.python.tasks.pex_build_task import pex_build

from .base_task import EnvironmentAwareDispatchTask

MYPY_BASE_CONFIG = """
[mypy]
explicit_package_bases = true
ignore_missing_imports = true
namespace_packages = true
pretty = true
show_column_numbers = true
show_error_codes = true
show_error_context = true
strict = true
warn_no_return = true
warn_redundant_casts = true
warn_unreachable = true
warn_unused_configs = true
warn_unused_ignores = true
"""


@dataclass
class MypyConfig:
    exclude_directories: Sequence[str] = ()
    """ A list of directories to exclude. """

    exclude_patterns: Sequence[str] = ()
    """ A list of regular expressions to match on files to exclude them."""

    global_overrides: Mapping[str, str | Sequence[str]] = field(default_factory=dict)
    """ Global overrides to place into the Mypy config under the `[mypy]` section."""

    module_overrides: Mapping[str, Mapping[str, str | Sequence[str]]] = field(default_factory=dict)
    """ Per-module overrides to place into the `[mypy-{key}]` section, where `{key}` is the key of the root mapping."""

    def dump(self) -> ConfigParser:
        config = ConfigParser(inline_comment_prefixes="#;")
        config.read(MYPY_BASE_CONFIG)

        if self.exclude_directories or self.exclude_patterns:
            exclude_patterns = []
            for dirname in self.exclude_directories or ():
                exclude_patterns.append("^" + re.escape(dirname.rstrip("/")) + "/.*$")
            exclude_patterns += self.exclude_patterns or ()
            exclude_regex = "(" + "|".join(exclude_patterns) + ")"
            config.set("mypy", "exclude", exclude_regex)
        for key, value in self.global_overrides.items():
            config.set("mypy", key, value if isinstance(value, str) else ",".join(value))
        for patterns, options in self.module_overrides.items():
            section = f"mypy-{patterns}"
            config.add_section(section)
            for key, value in options.items():
                config.set(section, key, value if isinstance(value, str) else ",".join(value))

        # config.set("mypy", "mypy_path", str(source_directory))

        return config

    def to_file(self, path: Path) -> None:
        config = self.dump()
        with path.open("w") as fp:
            config.write(fp)


class MypyTask(EnvironmentAwareDispatchTask):
    description = "Static type checking for Python code using Mypy."
    python_dependencies = ["mypy"]

    mypy_pex_bin: Property[Path | None] = Property.default(None)
    config: Property[MypyConfig | None] = Property.default(None)
    config_file: Property[Path | None] = Property.default(None)
    paths: Property[Sequence[str]] = Property.default_factory(list)
    additional_args: Property[Sequence[str]] = Property.default_factory(list)
    check_tests: Property[bool] = Property.default(True)
    use_daemon: Property[bool] = Property.default(True)
    python_version: Property[str]

    __config_file: Path | None = None

    # EnvironmentAwareDispatchTask

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str]:
        entry_point = "dmypy" if self.use_daemon.get() else "mypy"

        if mypy_pex_bin := self.mypy_pex_bin.get():
            # See https://pex.readthedocs.io/en/latest/api/vars.html
            env["PEX_SCRIPT"] = entry_point
            command = [str(mypy_pex_bin)]
        else:
            command = [entry_point]

        # TODO (@NiklasRosenstein): Should we add a task somewhere that ensures `.dmypy.json` is in `.gitignore`?
        #       Having it in the project directory makes it easier to just stop the daemon if it malfunctions (which
        #       happens regularly but is hard to detect automatically).

        status_file = (self.project.directory / ".dmypy.json").absolute()
        if self.use_daemon.get():
            command += ["--status-file", str(status_file), "run", "--"]
        if mypy_pex_bin:
            # Have mypy pick up the Python executable from the virtual environment that is activated automatically
            # during the execution of this task as this is an "EnvironmentAwareDispatchTask". If we don't supply this
            # option, MyPy will only know the packages in its PEX.
            command += ["--python-executable", "python"]
        if self.__config_file:
            command += ["--config-file", str(self.__config_file.absolute())]
        else:
            command += ["--show-error-codes", "--namespace-packages"]  # Sane defaults. 🙏
        if self.python_version.is_filled():
            command += ["--python-version", self.python_version.get()]

        command += [*self.paths.get()]
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        command += self.additional_args.get()
        return command

    # Task

    def prepare(self) -> TaskStatus | None:
        config = self.config.get()
        config_file = self.config_file.get()
        if config is not None and config_file is not None:
            raise RuntimeError("MypyTask.config and .config_file cannot be mixed")
        if config_file is None:
            config = config_file or MypyConfig()
            config_file = self.project.build_directory / self.name / "isort.ini"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config.to_file(config_file)
        self.__config_file = config_file
        return super().prepare()


def mypy(
    *,
    name: str = "python.mypy",
    project: Project | None = None,
    config: MypyConfig | None = None,
    config_file: Path | Supplier[Path] | None = None,
    paths: Sequence[str] | None = None,
    additional_args: Sequence[str] | Supplier[Sequence[str]] = (),
    check_tests: bool = True,
    use_daemon: bool = True,
    python_version: str | Supplier[str] | None = None,
    version_spec: str | None = None,
) -> MypyTask:
    """
    :param version_spec: If specified, the Mypy tool will be installed as a PEX and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()

    if version_spec is not None:
        mypy_pex_bin = pex_build(
            "mypy",
            requirements=[f"mypy{version_spec}"],
            console_script="mypy",
            project=project,
        ).output_file
    else:
        mypy_pex_bin = None

    if paths is None:
        paths = python_settings(project).get_source_paths()

    task = project.task(name, MypyTask, group="lint")
    task.mypy_pex_bin = mypy_pex_bin
    task.config = config
    task.config_file = config_file
    task.paths = paths
    task.additional_args = additional_args
    task.check_tests = check_tests
    task.use_daemon = use_daemon
    task.python_version = python_version
    return task
