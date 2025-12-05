from __future__ import annotations

import os
from collections.abc import MutableMapping, Sequence

from kraken.common import Supplier, intersect_paths
from kraken.core import Project, Property
from kraken.core.system.aspect import CheckAspect
from kraken.core.system.task import TaskStatus

from .base_task import EnvironmentAwareDispatchTask


class TyTask(EnvironmentAwareDispatchTask, CheckAspect.Implements):
    description = "Static type checking for Python code using Ty."
    python_dependencies = ["ty"]

    ty_cmd: Property[Sequence[str] | None] = Property.default(None)
    additional_args: Property[Sequence[str]] = Property.default_factory(list)
    check_tests: Property[bool] = Property.default(True)

    # EnvironmentAwareDispatchTask

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str] | TaskStatus:
        command: list[str] = []
        if ty_cmd := self.ty_cmd.get():
            command.extend(ty_cmd)
        command.append("ty")
        command.append("check")

        paths = [self.settings.source_directory]
        if self.check_tests.get():
            test_dir = self.settings.get_tests_directory()
            if test_dir is not None:
                paths.append(test_dir)
        paths += self.settings.lint_enforced_directories

        if opts := CheckAspect.current_options(self):
            if opts.paths:
                paths = intersect_paths(paths, opts.paths, left_relative_to=self.project.directory)
                if not paths:
                    return TaskStatus.skipped("no matching paths")

        command += map(os.fspath, paths)
        command += self.additional_args.get()
        return command


def ty(
    *,
    name: str = "python.ty",
    project: Project | None = None,
    additional_args: Sequence[str] | Supplier[Sequence[str]] = (),
    check_tests: bool = True,
    version_spec: str | None = None,
) -> TyTask:
    """
    :param version_spec: If specified, the Ty tool will be run via `uv tool run` and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()

    if version_spec is not None:
        ty_cmd = Supplier.of(["uv", "tool", "run", "--from", f"ty{version_spec}"])
    else:
        ty_cmd = None

    task = project.task(name, TyTask, group="lint")
    task.ty_cmd = ty_cmd
    task.additional_args = additional_args
    task.check_tests = check_tests
    return task
