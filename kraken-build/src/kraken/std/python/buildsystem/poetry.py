"""Implements Poetry as a build system for kraken-std."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from kraken.common import NotSet
from kraken.common.path import is_relative_to
from kraken.common.pyenv import get_current_venv
from kraken.common.toml import TomlFile
from kraken.core import TaskStatus
from kraken.std.python.pyproject import PackageIndex, PyprojectHandler
from kraken.std.python.settings import PythonSettings

from . import ManagedEnvironment, PythonBuildSystem

logger = logging.getLogger(__name__)


class PoetryPyprojectHandler(PyprojectHandler):
    """
    Pyproject configuration handler for Poetry projects.
    """

    def __init__(self, pyproj: TomlFile) -> None:
        super().__init__(pyproj)

    @property
    def _poetry_section(self) -> dict[str, Any]:
        return self.raw.setdefault("tool", {}).setdefault("poetry", {})  # type: ignore[no-any-return]

    def get_packages(self) -> list[PyprojectHandler.Package]:
        """
        Returns the packages included in the distribution of this project listed in `[tool.poetry.packages]`.

        If that configuration does not exist and *fallback* is set to True, the default that Poetry will
        assume is returned.
        """

        packages: list[dict[str, Any]] | None = self._poetry_section.get("packages")
        if packages is None:
            package_name = self._poetry_section["name"]
            return [self.Package(include=package_name.replace("-", "_").replace(".", "_"))]

        return [self.Package(include=p["include"], from_=p.get("from")) for p in packages]

    # PyprojectHandler

    def get_name(self) -> str:
        return self._poetry_section["name"]  # type: ignore[no-any-return]

    def get_version(self) -> str | None:
        return self._poetry_section.get("version")

    def get_python_version_constraint(self) -> str | None:
        return self._poetry_section.get("dependencies", {}).get("python")  # type: ignore[no-any-return]

    def set_version(self, version: str | None) -> None:
        project: dict[str, Any] = self._poetry_section
        if version is None:
            project.pop("version", None)
        else:
            project["version"] = version

    def get_package_indexes(self) -> list[PackageIndex]:
        sources = self._poetry_section.get("source", [])
        return [
            PackageIndex(
                alias=source["name"],
                index_url=source["url"],
                priority=PackageIndex.Priority[source["priority"]]
                if "priority" in source
                else (
                    PackageIndex.Priority.default
                    # Support deprecated source configurations.
                    if source.get("default")
                    else PackageIndex.Priority.secondary
                    if source.get("secondary")
                    else PackageIndex.Priority.supplemental
                ),
                verify_ssl=True,
            )
            for source in sources
        ]

    def set_package_indexes(self, indexes: Sequence[PackageIndex]) -> None:
        sources = self._poetry_section.setdefault("source", [])
        sources.clear()
        for index in indexes:
            if not index.verify_ssl:
                logger.warning(
                    "Poetry does not support disabling SSL verification for indexes (source: %s)", index.alias
                )
            sources.append(
                {
                    "name": index.alias,
                    "url": index.index_url,
                    "priority": index.priority.value,
                }
            )

    def set_path_dependencies_to_version(self, version: str) -> None:
        """
        Walks through the `[tool.poetry.dependencies]`, `[tool.poetry.dev-dependencies]`
        and `[tool.poetry.group.dev.dependencies]` groups to replace all path dependencies
        with proper index dependencies pointing using the specified `version` string.
        """

        def _dependency_groups() -> Iterator[tuple[str, dict[str, Any]]]:
            if dependencies := self._poetry_section.get("dependencies"):
                yield "dependencies", dependencies
            if dev_dependencies := self._poetry_section.get("dev-dependencies"):
                yield "dev-dependencies", dev_dependencies
            if group_dev_dependencies := self._poetry_section.get("group", {}).get("dev", {}).get("dependencies"):
                yield "group.dev.dependencies", group_dev_dependencies

        for name, dependencies in _dependency_groups():
            for key, value in list(dependencies.items()):
                if isinstance(value, dict) and "path" in value:
                    logger.debug("Replacing path dependency %s with version %s in %s", key, version, name)
                    dependencies[key] = version


class PoetryPythonBuildSystem(PythonBuildSystem):
    name = "Poetry"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    # PythonBuildSystem

    def get_pyproject_reader(self, pyproject: TomlFile) -> PoetryPyprojectHandler:
        return PoetryPyprojectHandler(pyproject)

    def supports_managed_environments(self) -> bool:
        return True

    def get_managed_environment(self) -> ManagedEnvironment:
        return PoetryManagedEnvironment(self.project_directory)

    def update_lockfile(self, settings: PythonSettings, pyproject: TomlFile) -> TaskStatus:
        command = ["poetry", "update"]
        logger.info("Run '%s'", " ".join(command))
        sp.check_call(command, cwd=self.project_directory)
        return TaskStatus.succeeded()

    def requires_login(self) -> bool:
        return True

    def login(self, settings: PythonSettings) -> None:
        for index in settings.package_indexes.values():
            if index.is_package_source and index.credentials:
                command = ["poetry", "config", "http-basic." + index.alias, index.credentials[0], index.credentials[1]]
                safe_command = ["poetry", "config", "http-basic." + index.alias, index.credentials[0], "MASKED"]
                logger.info("Run '%s'", " ".join(safe_command))
                code = sp.call(command)
                if code != 0:
                    raise RuntimeError(f"command {safe_command!r} failed with exit code {code}")

    def build(self, output_directory: Path) -> list[Path]:
        # Poetry does not allow configuring the output folder, so it's always going to be "dist/".
        # We remove the contents of that folder to make sure we know what was produced.
        dist_dir = self.project_directory / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        command = ["poetry", "build"]
        logger.info("Run '%s'", " ".join(command))
        sp.check_call(command, cwd=self.project_directory)
        src_files = list(dist_dir.iterdir())
        dst_files = [output_directory / path.name for path in src_files]
        for src, dst in zip(src_files, dst_files, strict=True):
            shutil.move(str(src), dst)

        # Unless the output directory is a subdirectory of the dist_dir, we remove the dist dir again.
        if not is_relative_to(output_directory, dist_dir):
            shutil.rmtree(dist_dir)

        return dst_files

    def get_lockfile(self) -> Path | None:
        return self.project_directory / "poetry.lock"


class PoetryManagedEnvironment(ManagedEnvironment):
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self._env_path: Path | None | NotSet = NotSet.Value

    def _get_current_poetry_environment_path(self) -> Path | None:
        """Uses `poetry env info -p`. This will not work if Poetry has to fall back to a compatible Python
        version if the version that Poetry is installed into is not compatible."""

        # Ensure we de-activate any environment that might be active when Kraken is invoked. Otherwise,
        # Poetry would fall back to that environment.
        environ = os.environ.copy()
        venv = get_current_venv(environ)
        if venv:
            venv.deactivate(environ)

        command = ["poetry", "env", "info", "-p"]
        logger.info("Run '%s'", " ".join(command))
        try:
            response = sp.check_output(command, cwd=self.project_directory, env=environ).decode().strip()
        except sp.CalledProcessError as exc:
            if exc.returncode != 1:
                raise
            return None

        return Path(response)

    def _get_all_poetry_known_environment_paths(self) -> list[Path]:
        """Uses `poetry env list --full-path` to get the path to all relevant virtual environments that are known
        to Poetry for the project. We fall back to this method if `poetry env info -p` fails us."""

        command = ["poetry", "env", "list", "--full-path"]
        try:
            response = sp.check_output(command, cwd=self.project_directory).decode().strip().splitlines()
        except sp.CalledProcessError as exc:
            if exc.returncode != 1:
                raise
            return []

        return [Path(line.replace(" (Activated)", "").strip()) for line in response if line]

    def _get_poetry_environment_path(self) -> Path | None:
        # Run the two Poetry commands we need to run in parallel to improve load times.
        with ThreadPoolExecutor() as executor:
            venv_path_future = executor.submit(self._get_current_poetry_environment_path)
            known_venvs_future = executor.submit(self._get_all_poetry_known_environment_paths)
            venv_path = venv_path_future.result()
            if venv_path is not None:
                return venv_path
            known_venvs = known_venvs_future.result()
            if known_venvs:
                if len(known_venvs) > 1:
                    logger.warning(
                        "This project has multiple Poetry environments. Picking the first one (%s)", known_venvs[0]
                    )
                return known_venvs[0]
            return None

    # ManagedEnvironment

    def exists(self) -> bool:
        try:
            return self.get_path().is_dir()
        except RuntimeError:
            return False

    def get_path(self) -> Path:
        if self._env_path is NotSet.Value:
            self._env_path = self._get_poetry_environment_path()
        if self._env_path is None:
            raise RuntimeError("Managed environment does not exist")
        return self._env_path

    def install(self, settings: PythonSettings) -> None:
        command = ["poetry", "install", "--no-interaction"]
        logger.info("Run '%s'", " ".join(command))
        sp.check_call(command, cwd=self.project_directory)
