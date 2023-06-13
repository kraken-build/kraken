""" Implements PDM as a build system for kraken-std. """

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
from pathlib import Path

from kraken.common import NotSet
from kraken.common.path import is_relative_to
from kraken.core import TaskStatus

from kraken.std.python.pyproject import PDMPyproject, Pyproject, SpecializedPyproject
from kraken.std.python.settings import PythonSettings

from . import ManagedEnvironment, PythonBuildSystem

logger = logging.getLogger(__name__)


def get_env_no_build_delete() -> dict[str, str]:
    env = os.environ.copy()
    env["PDM_BUILD_NO_CLEAN"] = "true"
    return env


class PDMPythonBuildSystem(PythonBuildSystem):
    name = "PDM"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    def get_pyproject_reader(self, pyproject: Pyproject) -> SpecializedPyproject:
        return PDMPyproject(pyproject)

    def supports_managed_environments(self) -> bool:
        return True

    def get_managed_environment(self) -> ManagedEnvironment:
        return PDMManagedEnvironment(self.project_directory)

    def update_pyproject(self, settings: PythonSettings, pyproject: Pyproject) -> None:
        pdm_pyproj = PDMPyproject(pyproject)
        for source in pdm_pyproj.get_sources():
            pdm_pyproj.delete_source(source["name"])
        for index in settings.package_indexes.values():
            if index.is_package_source:
                pdm_pyproj.upsert_source(index.alias, index.index_url, index.default, not index.default)

    def update_lockfile(self, settings: PythonSettings, pyproject: Pyproject) -> TaskStatus:
        command = ["pdm", "update"]
        sp.check_call(command, cwd=self.project_directory)
        return TaskStatus.succeeded()

    def requires_login(self) -> bool:
        return True

    def login(self, settings: PythonSettings) -> None:
        for index in settings.package_indexes.values():
            if index.is_package_source and index.credentials:
                commands = [
                    ["pdm", "config", f"pypi.{index.alias}.url", index.index_url],
                    [
                        "pdm",
                        "config",
                        f"pypi.{index.alias}.username",
                        index.credentials[0],
                    ],
                    [
                        "pdm",
                        "config",
                        f"pypi.{index.alias}.password",
                        index.credentials[1],
                    ],
                ]
                for command in commands:
                    safe_command = command[:-1] + ["MASKED"]
                    logger.info("$ %s", safe_command)

                    code = sp.call(command)
                    if code != 0:
                        raise RuntimeError(f"command {safe_command!r} failed with exit code {code}")

    def build(self, output_directory: Path, as_version: str | None = None) -> list[Path]:
        previous_version: str | None = None

        if as_version is not None:
            # Bump the in-source version number.
            pyproject = Pyproject.read(self.project_directory / "pyproject.toml")
            pdm_pyproj = PDMPyproject(pyproject)
            pdm_pyproj.update_relative_packages(as_version)
            previous_version = pdm_pyproj.set_version(as_version)
            pdm_pyproj.save()

        # PDM does not allow configuring the output folder, so it's always going to be "dist/".
        # We remove the contents of that folder to make sure we know what was produced.
        dist_dir = self.project_directory / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        command = ["pdm", "build"]

        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory, env=get_env_no_build_delete())
        src_files = list(dist_dir.iterdir())
        dst_files = [output_directory / path.name for path in src_files]
        os.makedirs(output_directory, exist_ok=True)
        for src, dst in zip(src_files, dst_files):
            shutil.move(str(src), dst)

        # Unless the output directory is a subdirectory of the dist_dir, we remove the dist dir again.
        if not is_relative_to(output_directory, dist_dir):
            shutil.rmtree(dist_dir)

        # Roll back the previously updated in-source version numbers.
        if previous_version is not None:
            pdm_pyproj = PDMPyproject(pyproject)
            pdm_pyproj.set_version(previous_version)
            pdm_pyproj.save()

        return dst_files


class PDMManagedEnvironment(ManagedEnvironment):
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self._env_path: Path | None | NotSet = NotSet.Value

    def _get_pdm_environment_path(self) -> None | Path:
        """Uses `pdm venv --path in-project`. TODO(simone.zandara) Add support for more environments."""

        create_command = [
            "pdm",
            "venv",
            "create",
        ]
        command = ["pdm", "venv", "--path", "in-project"]
        try:
            response = sp.check_output(command, cwd=self.project_directory).decode().strip().splitlines()
        except sp.CalledProcessError:
            # If there is no environment, create one and retrye
            try:
                response = sp.check_output(create_command, cwd=self.project_directory).decode().strip().splitlines()
            except sp.CalledProcessError as exc:
                if exc.returncode != 1:
                    raise
                return None

            # Retry to get the env path
            try:
                response = sp.check_output(command, cwd=self.project_directory).decode().strip().splitlines()
            except sp.CalledProcessError as exc:
                if exc.returncode != 1:
                    raise
                return None
            return None
        else:
            return [Path(line.replace(" (Activated)", "").strip()) for line in response if line][0]

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
        command = ["pdm", "install"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory, env=get_env_no_build_delete())
