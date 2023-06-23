""" Implements PDM as a build system for kraken-std. """

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
from pathlib import Path
from typing import Any, Sequence

from kraken.common import NotSet
from kraken.common.path import is_relative_to
from kraken.core import TaskStatus

from kraken.std.python.pyproject import PackageIndex, Pyproject, PyprojectHandler
from kraken.std.python.settings import PythonSettings

from . import ManagedEnvironment, PythonBuildSystem

logger = logging.getLogger(__name__)


def get_env_no_build_delete() -> dict[str, str]:
    env = os.environ.copy()
    env["PDM_BUILD_NO_CLEAN"] = "true"
    return env


class PdmPyprojectHandler(PyprojectHandler):
    """
    Implements the PyprojectHandler interface for PDM projects.
    """

    def __init__(self, pyproj: Pyproject) -> None:
        super().__init__(pyproj)

    # PyprojectHandler

    def get_package_indexes(self) -> list[PackageIndex]:
        results = []
        for source in self.raw.get("tool", {}).get("pdm", {}).get("source", []):
            if "username" in source or "password" in source:
                logger.warning(
                    "username/password in pyproject.toml [tool.pdm.source] is not supported, the information may "
                    "be lost (source name: %s)",
                    source["name"],
                )
            if source.get("type") == "find_links":
                logger.warning(
                    "source of type 'find_links' in pyproject.toml [tool.pdm.source] is not supported "
                    "(source name: %s)",
                    source["name"],
                )
                continue
            # TODO: To understand if a source is a "default" source as per Poetry's definition, we need
            #       to know if `pypi.ignore_stored_index` is set to `true`. It appears that this may be a
            #       local (for the project) or global (for the user) option. For now, we assume that this
            #       option is not turned on (as it is not by default) and all sources we find are primary
            #       sources instead of default sources. https://pdm.fming.dev/latest/usage/config/
            # TODO: We may also want to consider ensuring that respect-source-order is enabled, see
            #       https://pdm.fming.dev/latest/usage/config/#respect-the-order-of-the-sources
            results.append(
                PackageIndex(
                    alias=source["name"],
                    index_url=source["url"],
                    verify_ssl=source.get("verify_ssl", True),
                    priority=PackageIndex.Priority.primary,
                )
            )
        return results

    def set_package_indexes(self, indexes: Sequence[PackageIndex]) -> None:
        """
        Set the list of package indexes to the given list of indexes, replacing any existing indexes.

        Note that this only updates the package indexes in the `[tool.pdm.source]` section of the
        pyproject.toml file.
        See https://pdm.fming.dev/latest/usage/config/#source for more details.
        """

        sources_conf = self.raw.setdefault("tool", {}).setdefault("pdm", {}).setdefault("source", [])
        sources_conf.clear()

        # We don't currently support fully replicating the semantics of the index priority in PDM.
        # Instead, we treat all as primaries but add secondary/supplement to the end of the list.
        indexes = sorted(
            indexes,
            key=lambda x: 0
            if x.priority == PackageIndex.Priority.default
            else 1
            if x.priority == PackageIndex.Priority.primary
            else 2,
        )

        if any(x.priority == PackageIndex.Priority.default for x in indexes):
            logger.warning(
                "default index priority is not supported in %s, treating them as primary instead and "
                "putting them in front"
            )
        if any(x.priority in (PackageIndex.Priority.secondary, PackageIndex.Priority.supplemental) for x in indexes):
            logger.warning(
                "secondary/supplement index priority is not supported in %s, treating them as primary instead and "
                "putting them at the back"
            )

        for index in indexes:
            source_config: dict[str, Any] = {"name": index.alias, "url": index.index_url}
            if index.verify_ssl is False:
                source_config["verify_ssl"] = False
            sources_conf.append(source_config)


class PDMPythonBuildSystem(PythonBuildSystem):
    name = "PDM"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    def get_pyproject_reader(self, pyproject: Pyproject) -> PdmPyprojectHandler:
        return PdmPyprojectHandler(pyproject)

    def supports_managed_environments(self) -> bool:
        return True

    def get_managed_environment(self) -> ManagedEnvironment:
        return PDMManagedEnvironment(self.project_directory)

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
            pyproject = self.get_pyproject_reader(Pyproject.read(self.project_directory / "pyproject.toml"))
            previous_version = pyproject.get_version()
            pyproject.set_path_dependencies_to_version(as_version)
            pyproject.set_version(as_version)
            pyproject.raw.save()

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
            pyproject.set_version(previous_version)
            pyproject.raw.save()

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
