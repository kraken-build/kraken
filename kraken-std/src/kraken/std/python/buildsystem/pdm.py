""" Implements Pdm as a build system for kraken-std. """

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from kraken.common import NotSet
from kraken.common.path import is_relative_to
from kraken.common.pyenv import get_current_venv
from kraken.core import TaskStatus

from kraken.std.python.buildsystem.helpers import update_python_version_str_in_source_files
from kraken.std.python.pyproject import Pyproject
from kraken.std.python.settings import PythonSettings

from . import ManagedEnvironment, PythonBuildSystem

logger = logging.getLogger(__name__)


class PdmPythonBuildSystem(PythonBuildSystem):
    name = "Pdm"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    def supports_managed_environments(self) -> bool:
        return True

    def get_managed_environment(self) -> ManagedEnvironment:
        return PdmManagedEnvironment(self.project_directory)

    def update_pyproject(self, settings: PythonSettings, pyproject: Pyproject) -> None:
        for source in pyproject.get_pdm_sources():
            pyproject.delete_pdm_source(source["name"])
        for index in settings.package_indexes.values():
            if index.is_package_source:
                pyproject.upsert_pdm_source(index.alias, index.index_url, index.default, not index.default)

    def update_lockfile(self, settings: PythonSettings, pyproject: Pyproject) -> TaskStatus:
        command = ["pdm", "update"]
        sp.check_call(command, cwd=self.project_directory)
        return TaskStatus.succeeded()

    def requires_login(self) -> bool:
        return True

    def login(self, settings: PythonSettings) -> None:
        for index in settings.package_indexes.values():
            if index.is_package_source and index.credentials:
                username_command = ["pdm", "config", "pypi." + index.alias + ".username", index.credentials[0]]
                password_command = ["pdm", "config", "pypi." + index.alias + ".password", index.credentials[1]]
                safe_password_command = username_command[:-1] + ["MASKED"]
                logger.info("$ %s", username_command)
                logger.info("$ %s", safe_password_command)
                
                code = sp.call(username_command)
                if code != 0:
                    raise RuntimeError(f"command {username_command!r} failed with exit code {code}")

                code = sp.call(password_command)
                if code != 0:
                    raise RuntimeError(f"command {password_command!r} failed with exit code {code}")

    def build(self, output_directory: Path, as_version: str | None = None) -> list[Path]:
        previous_version: str | None = None
        revert_version_paths: list[Path] = []
        if as_version is not None:
            # Bump the in-source version number.
            pyproject = Pyproject.read(self.project_directory / "pyproject.toml")
            pyproject.update_relative_packages(as_version)
            previous_version = pyproject.set_pdm_version(as_version)
            pyproject.save()
            for package in pyproject.get_pdm_packages(fallback=True):
                package_dir = self.project_directory / (package.from_ or "") / package.include
                n_replaced = update_python_version_str_in_source_files(as_version, package_dir)
                if n_replaced > 0:
                    revert_version_paths.append(package_dir)
                    print(
                        f"Bumped {n_replaced} version reference(s) in "
                        f"{package_dir.relative_to(self.project_directory)} to {as_version}"
                    )

        # Pdm does not allow configuring the output folder, so it's always going to be "dist/".
        # We remove the contents of that folder to make sure we know what was produced.
        dist_dir = self.project_directory / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        command = ["pdm", "build"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory)
        src_files = list(dist_dir.iterdir())
        dst_files = [output_directory / path.name for path in src_files]
        for src, dst in zip(src_files, dst_files):
            shutil.move(str(src), dst)

        # Unless the output directory is a subdirectory of the dist_dir, we remove the dist dir again.
        if not is_relative_to(output_directory, dist_dir):
            shutil.rmtree(dist_dir)

        # Roll back the previously updated in-source version numbers.
        if previous_version is not None:
            pyproject.set_pdm_version(previous_version)
            pyproject.save()
            for package_dir in revert_version_paths:
                update_python_version_str_in_source_files(previous_version, package_dir)

        return dst_files


class PdmManagedEnvironment(ManagedEnvironment):
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self._env_path: Path | None | NotSet = NotSet.Value

    def _get_pdm_environment_path(self) -> list[Path]:
        """Uses `pdm venv --path in-project`. TODO(simone.zandara) Add support for more environments. """

        command = ["pdm", "venv", "--path", "in-project"]
        try:
            response = sp.check_output(command, cwd=self.project_directory).decode().strip().splitlines()
        except sp.CalledProcessError as exc:
            if exc.returncode != 1:
                raise
            return []
        else:
            return [Path(line.replace(" (Activated)", "").strip()) for line in response if line]

    # ManagedEnvironment

    def exists(self) -> bool:
        try:
            self.get_path()
            return True
        except RuntimeError:
            return False

    def get_path(self) -> Path:
        if self._env_path is NotSet.Value:
            self._env_path = self._get_pdm_environment_path()
        if self._env_path is None:
            raise RuntimeError("managed environment does not exist")
        return self._env_path

    def install(self, settings: PythonSettings) -> None:
        command = ["pdm", "install", "--no-interaction"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory)
