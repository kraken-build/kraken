from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from dataclasses import dataclass
from itertools import chain
from os import fspath
from pathlib import Path

from kraken.common import intersect_paths
from kraken.core import Aspect, FmtAspect, LintAspect, Project, Property, Supplier, TaskStatus

from .base_task import EnvironmentAwareDispatchTask


class RuffTask(EnvironmentAwareDispatchTask, LintAspect.Implements, FmtAspect.Implements):
    """A task to run `ruff` in either format, fix, or check mode."""

    description = "Lint Python source files with Ruff."
    python_dependencies = ["ruff"]

    ruff_cmd: Property[Sequence[str]] = Property.default(["ruff"])
    ruff_task: Property[Sequence[str]] = Property.default_factory(list)
    config_file: Property[Path]
    additional_args: Property[Sequence[str]] = Property.default_factory(list)

    _aspect_disabled: bool = False
    """
    The [ruff] function creates separate fix/check tasks, which we don't need when invoking Ruff via aspects
    since the `--fix` and `--check` options can be passed via the aspect options. We enable `ignore_aspects` for
    these tasks do they don't get also invoked with the aspect.
    """

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str] | TaskStatus:
        ruff_args = list(self.ruff_task.get())
        ruff_paths: list[Path] = [self.settings.source_directory]
        if tests_dir := self.settings.get_tests_directory():
            ruff_paths.append(tests_dir)

        if ruff_args[0] == "check" and (lint := LintAspect.current_options(self)):
            if lint.fix and "--fix" not in ruff_args:
                ruff_args += ["--fix"]
            if lint.unsafe_fix and "--unsafe-fix" not in ruff_args:
                ruff_args += ["--unsafe-fix"]
            ruff_paths = intersect_paths(ruff_paths, lint.paths, left_relative_to=self.project.directory)

        if ruff_args[0] == "format" and (fmt := FmtAspect.current_options(self)):
            if fmt.check and "--check" not in ruff_args:
                ruff_args += ["--check"]
            ruff_paths = intersect_paths(ruff_paths, fmt.paths, left_relative_to=self.project.directory)

        if not ruff_paths:
            return TaskStatus.skipped("no matching paths")

        command = [*self.ruff_cmd.get(), *ruff_args, *map(fspath, ruff_paths)]
        command += [str(directory) for directory in self.settings.lint_enforced_directories]
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get().absolute())]
        command += self.additional_args.get()
        return command

    def aspect_applies(self, aspect: Aspect) -> bool:
        if self._aspect_disabled:
            return False
        task = self.ruff_task.get()[0]
        match (task, aspect):
            case ("format", FmtAspect()) | ("check", LintAspect()):
                return True
        return False


@dataclass
class RuffTasks:
    check: RuffTask
    fix: RuffTask
    fmt: RuffTask
    fmt_check: RuffTask


def ruff(
    *,
    name: str = "python.ruff",
    project: Project | None = None,
    config_file: Path | Supplier[Path] | None = None,
    additional_args: Sequence[str] | Supplier[Sequence[str]] = (),
    additional_requirements: Sequence[str] = (),
    version_spec: str | None = "~=0.14.0",
) -> RuffTasks:
    """Creates three tasks for formatting and linting your Python project with Ruff.

    :param name: Prefix name for the ruff tasks.
    :param project: Project used for the generated ruff tasks. If not specified will consider `Project.current()`.
    :param config_file: Configuration file to consider.
    :param additional_args: Additional arguments to pass to all ruff tasks.
    :param additional_requirements: Additional requirements to pass to `uv tool run`.
    :param version_spec: If specified, the ruff tool will be run via `uv tool run` and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()

    if version_spec is not None:
        ruff_cmd = Supplier.of(
            [
                "uv",
                "tool",
                "run",
                "--from",
                f"ruff{version_spec}",
                *chain.from_iterable(("--with", r) for r in additional_requirements),
                "ruff",
            ]
        )
    else:
        ruff_cmd = Supplier.of(["ruff"])

    check_task = project.task(f"{name}.check", RuffTask, group="lint")
    check_task.ruff_cmd = ruff_cmd
    check_task.ruff_task = ["check"]
    check_task.config_file = config_file
    check_task.additional_args = additional_args

    fix_task = project.task(f"{name}.fix", RuffTask, group="fmt")
    fix_task.ruff_cmd = ruff_cmd
    fix_task.ruff_task = ["check", "--fix"]
    fix_task.config_file = config_file
    fix_task.additional_args = additional_args
    fix_task._aspect_disabled = True

    format_task = project.task(f"{name}.fmt", RuffTask, group="fmt")
    format_task.ruff_cmd = ruff_cmd
    format_task.ruff_task = ["format"]
    format_task.config_file = config_file
    format_task.additional_args = additional_args

    format_check_task = project.task(f"{name}.fmt.check", RuffTask, group="lint")
    format_check_task.ruff_cmd = ruff_cmd
    format_check_task.ruff_task = ["format", "--check"]
    format_check_task.config_file = config_file
    format_check_task.additional_args = additional_args
    format_check_task._aspect_disabled = True

    return RuffTasks(check_task, fix_task, format_task, format_check_task)
