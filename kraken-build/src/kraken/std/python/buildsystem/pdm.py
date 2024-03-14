""" Implements PDM as a build system for kraken-std. """

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from kraken.common import NotSet
from kraken.common.path import is_relative_to
from kraken.core import TaskStatus
from kraken.std.python.pyproject import PackageIndex, Pyproject, PyprojectHandler
from kraken.std.python.settings import PythonSettings

from . import ManagedEnvironment, PythonBuildSystem

logger = logging.getLogger(__name__)


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
        if any(x.priority == PackageIndex.Priority.default for x in indexes):
            logger.warning(
                "default index priority is not supported in %s, treating them as primary instead and "
                "putting them in front",
                type(self).__name__,
            )
        if any(x.priority in (PackageIndex.Priority.secondary, PackageIndex.Priority.supplemental) for x in indexes):
            logger.warning(
                "secondary/supplement index priority is not supported in %s, treating them as primary instead and "
                "putting them at the back",
                type(self).__name__,
            )
        indexes = sorted(
            indexes,
            key=lambda x: 0
            if x.priority == PackageIndex.Priority.default
            else 1
            if x.priority == PackageIndex.Priority.primary
            else 2,
        )

        for index in indexes:
            source: dict[str, Any] = {"name": index.alias, "url": index.index_url}
            if index.verify_ssl is False:
                source["verify_ssl"] = False
            sources_conf.append(source)

    def get_packages(self) -> list[PyprojectHandler.Package]:
        # TODO: Detect packages in the PDM project. Until we do, the __version__ in source files of PDM
        #       projects are not bumped on publish.
        return []


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

    def build(self, output_directory: Path) -> list[Path]:
        # PDM does not allow configuring the output folder, so it's always going to be "dist/".
        # We remove the contents of that folder to make sure we know what was produced.
        dist_dir = self.project_directory / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        command = ["pdm", "build"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory)

        src_files = list(dist_dir.iterdir())
        dst_files = [output_directory / path.name for path in src_files]
        os.makedirs(output_directory, exist_ok=True)
        for src, dst in zip(src_files, dst_files):
            shutil.move(str(src), dst)

        # Unless the output directory is a subdirectory of the dist_dir, we remove the dist dir again.
        if not is_relative_to(output_directory, dist_dir):
            shutil.rmtree(dist_dir)

        return dst_files

    def get_lockfile(self) -> Path | None:
        return self.project_directory / "pdm.lock"


class PDMManagedEnvironment(ManagedEnvironment):
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self._env_path: Path | None | NotSet = NotSet.Value

    def _get_pdm_environment_path(self, create: bool) -> None | Path:
        """Uses `pdm venv --path in-project`. TODO(simone.zandara) Add support for more environments."""

        get_command = ["pdm", "venv", "--path", "in-project"]
        logger.debug("$ %s", get_command)
        try:
            return Path(sp.check_output(get_command, cwd=self.project_directory, stderr=sp.PIPE).decode().strip())
        except sp.CalledProcessError as exc:
            logger.debug("pdm venv --path failed with exit code %s, output: %s", exc.returncode, exc.stderr.decode())
            if not create:
                return None

        create_command = ["pdm", "venv", "create"]
        logger.info("$ %s", create_command)
        sp.check_call(create_command, cwd=self.project_directory)

        # Make sure we use the in-project environment.
        use_command = ["pdm", "use", "--venv", "in-project"]
        logger.info("$ %s", use_command)
        sp.check_call(use_command, cwd=self.project_directory)

        path = self._get_pdm_environment_path(create=False)
        if path is None:
            raise RuntimeError("Failed to create PDM environment")

        return path

    # ManagedEnvironment

    def exists(self) -> bool:
        try:
            self.get_path()
            return True
        except RuntimeError:
            return False

    def get_path(self) -> Path:
        if self._env_path is NotSet.Value:
            self._env_path = self._get_pdm_environment_path(create=False)
        if self._env_path is None:
            raise RuntimeError("managed environment does not exist")
        return self._env_path

    def install(self, settings: PythonSettings) -> None:
        self._get_pdm_environment_path(create=True)

        command = ["pdm", "install"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory)
