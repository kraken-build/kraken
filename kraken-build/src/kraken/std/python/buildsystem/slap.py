"""Implements Slap as a Python build system for kraken-std.

Requires at least Slap 1.6.25."""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess as sp
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from kraken.common import NotSet
from kraken.common.toml import TomlFile
from kraken.core import TaskStatus
from kraken.std.python.pyproject import PackageIndex, PyprojectHandler

from . import ManagedEnvironment, PythonBuildSystem
from .pdm import PdmPyprojectHandler, PDMPythonBuildSystem
from .poetry import PoetryPyprojectHandler, PoetryPythonBuildSystem

if TYPE_CHECKING:
    from ..settings import PythonSettings

logger = logging.getLogger(__name__)


class SlapPythonBuildSystem(PythonBuildSystem):
    name = "Slap"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    def get_pyproject_reader(self, pyproject: TomlFile) -> PyprojectHandler:
        if "poetry" in pyproject.get("tool", {}):
            return PoetryPyprojectHandler(pyproject)
        if "pdm" in pyproject.get("build-backend", {}):
            return PdmPyprojectHandler(pyproject)
        raise NotImplementedError("Don't know this build system")

    def supports_managed_environments(self) -> bool:
        return True

    def get_managed_environment(self) -> ManagedEnvironment:
        return SlapManagedEnvironment(self.project_directory)

    def update_pyproject(self, settings: PythonSettings, pyproject: TomlFile) -> None:
        if "poetry" in pyproject.get("tool", {}):
            PoetryPythonBuildSystem(self.project_directory).update_pyproject(settings, pyproject)
        if "pdm" in pyproject.get("tool", {}):
            PDMPythonBuildSystem(self.project_directory).update_pyproject(settings, pyproject)

    def update_lockfile(self, settings: PythonSettings, pyproject: TomlFile) -> TaskStatus:
        return TaskStatus.skipped("not supported")

    def requires_login(self) -> bool:
        return False

    @contextlib.contextmanager
    def bump_version(self, version: str) -> Iterator[None]:
        # TODO (@NiklasRosenstein): We should find a way to revert the changes to the worktree
        #       that this command does.
        command = ["slap", "release", version]
        logger.info("Run '%s'", " ".join(command))
        sp.check_call(command, cwd=self.project_directory)
        yield

    def build(self, output_directory: Path) -> list[Path]:
        with tempfile.TemporaryDirectory() as tempdir:
            command = ["slap", "publish", "--dry", "-b", tempdir]
            logger.info("Running %s in '%s'", command, self.project_directory)
            sp.check_call(command, cwd=self.project_directory)

            src_files = list(Path(tempdir).iterdir())
            dst_files = [output_directory / path.name for path in src_files]
            for src, dst in zip(src_files, dst_files, strict=True):
                shutil.move(str(src), dst)
        return dst_files

    def get_lockfile(self) -> Path | None:
        return None


class SlapManagedEnvironment(ManagedEnvironment):
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self._env_path: Path | None | NotSet = NotSet.Value

    def exists(self) -> bool:
        try:
            self.get_path()
            return True
        except RuntimeError:
            return False

    def get_path(self) -> Path:
        if self._env_path is NotSet.Value:
            command = ["slap", "venv", "-p"]
            logger.info("Run '%s'", " ".join(command))
            try:
                self._env_path = Path(
                    sp.check_output(command, cwd=self.project_directory, stderr=sp.DEVNULL).decode().strip()
                )
            except sp.CalledProcessError as exc:
                if exc.returncode != 1:
                    raise
                self._env_path = None
        if self._env_path is None:
            raise RuntimeError("managed environment does not exist")
        return self._env_path

    def install(self, settings: PythonSettings) -> None:
        # Ensure that an environment exists.
        if not self.exists():
            command = ["slap", "venv", "-ac"]
            logger.info("Run '%s'", " ".join(command))
            sp.check_call(command, cwd=self.project_directory)

        # Install into the environment.
        command = ["slap", "install", "--ignore-active-venv", "--link"]
        safe_command = list(command)
        for index in settings.package_indexes.values():
            if index.is_package_source:
                spec = f"name={quote(index.alias)},url={quote(index.index_url)}"
                if index.credentials:
                    spec += f",username={quote(index.credentials[0])},password={quote(index.credentials[1])}"
                safe_spec = spec.replace(quote(index.credentials[1]), "[MASKED]") if index.credentials else spec
                option = "--index" if index.priority.value == PackageIndex.Priority.default.value else "--extra-index"
                command += [option, spec]
                safe_command += [option, safe_spec]

        logger.info("Run '%s'", " ".join(safe_command))
        sp.check_call(command, cwd=self.project_directory)
