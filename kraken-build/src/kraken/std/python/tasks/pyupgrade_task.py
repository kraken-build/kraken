from __future__ import annotations

import dataclasses
from collections.abc import Collection, Iterable, Sequence
from difflib import unified_diff
from pathlib import Path
from sys import stdout
from tempfile import TemporaryDirectory

from kraken.common.supplier import Supplier
from kraken.core import Project, Property, TaskStatus
from kraken.std.python.tasks.pex_build_task import pex_build

from .. import python_settings
from .base_task import EnvironmentAwareDispatchTask


class PyUpgradeTask(EnvironmentAwareDispatchTask):
    description = "Upgrades to newer Python syntax sugars with pyupgrade."
    python_dependencies = ["pyupgrade"]

    pyupgrade_bin: Property[str] = Property.default("pyupgrade")
    keep_runtime_typing: Property[bool] = Property.default(False)
    additional_files: Property[Sequence[Path]] = Property.default_factory(list)
    python_version: Property[str]

    # EnvironmentAwareDispatchTask

    def get_execute_command(self) -> list[str]:
        return self.run_pyupgrade(self.additional_files.get(), ("--exit-zero-even-if-changed",))

    def run_pyupgrade(self, files: Iterable[Path], extra: Iterable[str]) -> list[str]:
        command = [self.pyupgrade_bin.get(), f"--py{self.python_version.get_or('3').replace('.', '')}-plus", *extra]
        if self.keep_runtime_typing.get():
            command.append("--keep-runtime-typing")
        command.extend(str(f) for f in files)
        return command


class PyUpgradeCheckTask(PyUpgradeTask):
    description = "Check Python source files syntax sugars with pyupgrade."
    python_dependencies = ["pyupgrade"]

    keep_runtime_typing: Property[bool] = Property.default(False)
    additional_files: Property[Sequence[Path]] = Property.default_factory(list)
    python_version: Property[str]

    def execute(self) -> TaskStatus:
        # We copy the file because there is no way to make pyupgrade not edit the files
        old_dir = self.settings.project.directory.resolve()
        new_file_for_old_file = {}
        with TemporaryDirectory() as new_dir:
            for file in self.additional_files.get():
                new_file = new_dir / file.resolve().relative_to(old_dir)
                new_file.parent.mkdir(parents=True, exist_ok=True)
                new_file.write_bytes(file.read_bytes())
                new_file_for_old_file[file] = new_file
            self._files = new_file_for_old_file.values()

            result = super().execute()
            if not result.is_failed():
                return result  # nothing more to do

            # We print a diff
            for old_file, new_file in new_file_for_old_file.items():
                old_content = old_file.read_text()
                new_content = new_file.read_text()
                if old_content != new_content:
                    stdout.writelines(
                        unified_diff(
                            old_content.splitlines(keepends=True),
                            new_content.splitlines(keepends=True),
                            fromfile=str(old_file),
                            tofile=str(old_file),
                            n=5,
                        )
                    )
            return result

    def get_execute_command(self) -> list[str]:
        return self.run_pyupgrade(self._files, ())


@dataclasses.dataclass
class PyUpgradeTasks:
    check: PyUpgradeTask
    format: PyUpgradeTask


def pyupgrade(
    *,
    name: str = "python.pyupgrade",
    project: Project | None = None,
    exclude: Collection[Path] = (),
    exclude_patterns: Collection[str] = (),
    keep_runtime_typing: bool = False,
    python_version: str = "3",
    additional_files: Sequence[Path] = (),
    version_spec: str | None = None,
) -> PyUpgradeTasks:
    """
    :param version_spec: If specified, the pyupgrade tool will be installed as a PEX and does not need to be installed
        into the Python project's virtual env.
    """

    project = project or Project.current()

    if version_spec is not None:
        pyupgrade_bin = pex_build(
            "pyupgrade", requirements=[f"pyupgrade{version_spec}"], console_script="pyupgrade", project=project
        ).output_file.map(str)
    else:
        pyupgrade_bin = Supplier.of("pyupgrade")

    settings = python_settings(project)

    directories = list(additional_files)
    directories.append(project.directory / settings.source_directory)
    test_directory = settings.get_tests_directory()
    if test_directory is not None:
        directories.append(project.directory / test_directory)
    files = {f.resolve() for p in directories for f in Path(p).glob("**/*.py")}
    exclude = [e.resolve() for e in exclude]
    filtered_files = [
        f
        for f in files
        if not any(f.is_relative_to(i) for i in exclude) and not any(f.match(p) for p in exclude_patterns)
    ]

    check_task = project.task(f"{name}.check", PyUpgradeCheckTask, group="lint")
    check_task.pyupgrade_bin = pyupgrade_bin
    check_task.additional_files = filtered_files
    check_task.keep_runtime_typing = keep_runtime_typing
    check_task.python_version = python_version

    format_task = project.task(name, PyUpgradeTask, group="fmt")
    format_task.pyupgrade_bin = pyupgrade_bin
    format_task.additional_files = filtered_files
    format_task.keep_runtime_typing = keep_runtime_typing
    format_task.python_version = python_version

    return PyUpgradeTasks(check_task, format_task)
