"""
Experimental.

Support for Python projects managed by [UV](https://docs.astral.sh/uv/guides/projects/).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Iterable, TypeVar

from kraken.common import NotSet
from kraken.common.pyenv import get_current_venv
from kraken.common.toml import TomlFile
from kraken.core import TaskStatus
from kraken.std.python.pyproject import PackageIndex, PyprojectHandler
from kraken.std.python.settings import PythonSettings
from kraken.std.util.url import inject_url_credentials

from . import ManagedEnvironment, PythonBuildSystem

logger = logging.getLogger(__name__)
T = TypeVar("T")
Safe = Annotated[T, "safe"]
Unsafe = Annotated[T, "unsafe"]


@dataclass
class UvIndex:
    # https://docs.astral.sh/uv/configuration/indexes/#defining-an-index
    url: str
    name: str | None = None
    default: bool = False
    explicit: bool = False
    credentials: tuple[str, str] | None = None

    @property
    def safe_url(self) -> str:
        if self.credentials:
            return inject_url_credentials(self.url, self.credentials[0], "[MASKED]")
        return self.url

    @property
    def unsafe_url(self) -> str:
        if self.credentials:
            return inject_url_credentials(self.url, self.credentials[0], self.credentials[1])
        return self.url

    @staticmethod
    def of(index: PackageIndex) -> "UvIndex":
        credentials = index.credentials if isinstance(index, PythonSettings._PackageIndex) else None
        return UvIndex(
            index.index_url,
            name=index.alias if index.alias != "" else None,
            default=index.priority == index.Priority.default,
            explicit=index.priority == index.Priority.explicit,
            credentials=credentials,
        )


@dataclass
class UvIndexes:
    indexes: list[UvIndex]

    def __post_init__(self) -> None:
        if len([index for index in self.indexes if index.default]) > 1:
            raise ValueError("There can be only one default index.")

    @classmethod
    def from_package_indexes(cls, indexes: Iterable[PackageIndex]) -> "UvIndexes":
        indexes = sorted(indexes, key=lambda index: index.priority.level)
        return cls([UvIndex.of(index) for index in indexes])

    def to_safe_args(self) -> list[str]:
        """Create a list of arguments for UV with sensitive information masked."""
        args: list[str] = []
        for index in self.indexes:
            args += ["--default-index" if index.default else "--index", index.safe_url]
        return args

    def to_unsafe_args(self) -> list[str]:
        """Create a list of arguments for UV with sensitive information in plaintext."""

        args: list[str] = []
        for index in self.indexes:
            args += ["--default-index" if index.default else "--index", index.unsafe_url]
        return args

    def to_config(self) -> list[dict[str, Any]]:
        """Inject UV configuration for indexes into a configuration."""
        entries: list[dict[str, str | bool]] = []
        for index in self.indexes:
            entry: dict[str, Any] = {}
            if index.name is not None and index.name != "":
                entry["name"] = index.name
            entry["url"] = index.url
            if index.default:
                entry["default"] = True
            if index.explicit:
                entry["explicit"] = True
            entries.append(entry)
        return entries

    def to_env(self) -> dict[str, str]:
        """Convert UV configuration for indexes into environment variables."""

        env = {}
        uv_indexes = []
        for index in self.indexes:
            if index.default:
                # https://docs.astral.sh/uv/configuration/environment/#uv_default_index
                env["UV_DEFAULT_INDEX"] = index.unsafe_url
            else:
                # https://docs.astral.sh/uv/configuration/environment/#uv_index
                uv_indexes.append(
                    (f"{index.name}=" if index.name is not None and index.name != "" else "") + index.unsafe_url
                )

        if len(uv_indexes) != 0:
            env["UV_INDEX"] = " ".join(uv_indexes)
        return env


class UvPyprojectHandler(PyprojectHandler):
    """Implements the PyprojectHandler interface for UV projects."""

    # TODO: Support global `uv.toml` configuration file?

    def get_package_indexes(self) -> list[PackageIndex]:
        """Maps the UV [`index`][1] table, [`index-url`][2] and [`extra-index-url`][3] options to Kraken's concept of
        package indices. Note that UV does not support the concept of "aliases" for package indices, so instead
        the package index alias is ignored and generated automatically based on the hostname and URL hash.

        [1]: https://docs.astral.sh/uv/reference/settings/#index
        [2]: https://docs.astral.sh/uv/reference/settings/#index-url
        [3]: https://docs.astral.sh/uv/reference/settings/#extra-index-url
        """

        indexes: list[PackageIndex] = []
        for index in self.raw.get("tool", {}).get("uv", {}).get("index", []):
            indexes.append(
                PackageIndex(
                    alias=index.get("name", ""),
                    index_url=index["url"],
                    priority=PackageIndex.Priority.default
                    if index.get("default", False)
                    else PackageIndex.Priority.explicit
                    if index.get("explicit", False)
                    else PackageIndex.Priority.supplemental,
                    verify_ssl=True,
                )
            )

        if index_url := self.raw.get("tool", {}).get("uv", {}).get("index-url"):
            indexes.append(
                PackageIndex(
                    alias="",  # unnamed index
                    index_url=index_url,
                    # can it be default is there is already one above ?
                    priority=PackageIndex.Priority.default,
                    verify_ssl=True,
                )
            )

        for index_url in self.raw.get("tool", {}).get("uv", {}).get("extra-index-url", []):
            indexes.append(
                PackageIndex(
                    alias="",  # unnamed index
                    index_url=index_url,
                    priority=PackageIndex.Priority.supplemental,
                    verify_ssl=True,
                )
            )
        return indexes

    def set_package_indexes(self, indexes: Sequence[PackageIndex]) -> None:
        """Counterpart to [`get_package_indexes()`], check there."""
        root_config = self.raw.get("tool", {}).get("uv", {})

        # deprecated fields
        root_config.pop("index-url", None)
        root_config.pop("extra-index-url", None)

        config = self.raw.setdefault("tool", {}).setdefault("uv", {}).setdefault("index", [])
        config.clear()
        config.extend(UvIndexes.from_package_indexes(indexes).to_config())

    def get_packages(self) -> list[PyprojectHandler.Package]:
        package_name = self.raw["project"]["name"]
        return [self.Package(include=package_name.replace("-", "_").replace(".", "_"))]

    def _get_sources(self) -> dict[str, dict[str, Any]]:
        return self.raw.get("tool", {}).get("uv", {}).get("sources", {})  # type: ignore [no-any-return]

    def _get_dependencies(self) -> list[str]:
        """Fetches dependencies following [PEP631](https://peps.python.org/pep-0631/) format."""
        return self.raw.get("project", {}).get("dependencies", [])  # type: ignore [no-any-return]

    def _get_dependency_groups(self) -> dict[str, list[str]]:
        return self.raw.get("dependency-groups", {})

    def _get_optional_dependencies(self) -> dict[str, list[str]]:
        return self.raw.get("project", {}).get("optional-dependencies", {})  # type: ignore [no-any-return]

    def set_path_dependencies_to_version(self, version: str) -> None:
        """
        Walks through the `[project.dependencies]`, `[project.dependency-groups]`
        and `[project.optional-dependencies]` groups to replace all path and workspace sources
        with proper index dependencies using the specified `version` string.

        Based on [PEP631](https://peps.python.org/pep-0631/) for dependencies and optional-dependencies,
        and [PEP735](https://peps.python.org/pep-0735/) for dependency-groups.
        """

        sources = self._get_sources()
        dependencies = self._get_dependencies()
        dependency_groups = self._get_dependency_groups()
        optional_dependencies = self._get_optional_dependencies()
        sources_to_rm: set[str] = set()
        for source, params in sources.items():
            # TODO(Ghelfi): Check if entry with `path` is within the current project
            if "workspace" in params or "path" in params:
                sources_to_rm.add(source)
                if source in dependencies:
                    index = dependencies.index(source)
                    dependencies[index] = f"{source}=={version}"
                for key, deps in dependency_groups.items():
                    if source in deps:
                        index = deps.index(source)
                        dependency_groups[key][index] = f"{source}=={version}"
                for key, deps in optional_dependencies.items():
                    if source in deps:
                        index = deps.index(source)
                        optional_dependencies[key][index] = f"{source}=={version}"

        for elem in sources_to_rm:
            sources.pop(elem)


class UvPythonBuildSystem(PythonBuildSystem):
    """
    Implements Python build-system capabilities for [UV].

    [UV]: https://docs.astral.sh/uv/guides/projects/
    """

    name = "UV"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    def get_pyproject_reader(self, pyproject: TomlFile) -> UvPyprojectHandler:
        return UvPyprojectHandler(pyproject)

    def supports_managed_environments(self) -> bool:
        return True

    def get_managed_environment(self) -> ManagedEnvironment:
        return UvManagedEnvironment(self.project_directory)

    def update_lockfile(self, settings: PythonSettings, pyproject: TomlFile) -> TaskStatus:
        _run_with_uv_indexes(["uv", "lock", "--upgrade"], settings, self.project_directory)
        return TaskStatus.succeeded()

    def requires_login(self) -> bool:
        # TODO: implement when uv supports keyring
        # https://github.com/astral-sh/uv/issues/8810
        return False

    # TODO: Implement bump_version()

    def build_v2(self, settings: PythonSettings, output_directory: Path) -> list[Path]:
        """
        Uses [build] `>=1.0.0,<2.0.0` to build a distribution of the Python project.

        [build]: https://pypi.org/project/build/
        """
        # Making sure the build directory is clean
        dist_dir = output_directory.absolute()
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        _run_with_uv_indexes(["uv", "build", f"--out-dir={dist_dir}"], settings, self.project_directory)
        return list(f for f in output_directory.iterdir() if f.is_file() and not f.name.startswith("."))

    def get_lockfile(self) -> Path | None:
        return self.project_directory / "uv.lock"


class UvManagedEnvironment(ManagedEnvironment):
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self._env_path: Path | None | NotSet = NotSet.Value

    def _get_uv_environment_path(self) -> Path | None:
        """Uses `uv run` to determines the location of the venv."""

        # Ensure we de-activate any environment that might be active when Kraken is invoked. Otherwise,
        # Poetry would fall back to that environment.
        environ = os.environ.copy()
        venv = get_current_venv(environ)
        if venv:
            venv.deactivate(environ)

        # Run inside venv without updating lock file and venv. Therefore this doesn't require index credentials.
        command = ["uv", "run", "--frozen", "--no-sync", "bash", "-c", "printenv VIRTUAL_ENV"]
        logger.debug("Detecting virtual environment ... %s", " ".join(command))
        try:
            response = sp.check_output(command, cwd=self.project_directory, env=environ).decode().strip()
        except sp.CalledProcessError as exc:
            if exc.returncode != 1:
                raise
            return None

        logger.info("Virtual environment detected: %s", response)
        return Path(response)

    # ManagedEnvironment

    def exists(self) -> bool:
        try:
            return self.get_path().is_dir()
        except RuntimeError:
            return False

    def get_path(self) -> Path:
        if self._env_path is NotSet.Value:
            self._env_path = self._get_uv_environment_path()
        if self._env_path is None:
            raise RuntimeError("Managed environment does not exist")
        return self._env_path

    def install(self, settings: PythonSettings) -> None:
        # --locked is used only when uv.lock is present
        cmd = ["uv", "sync", "--all-packages"]
        if (self.project_directory / "uv.lock").is_file():
            cmd.append("--locked")

        _run_with_uv_indexes(
            cmd,
            settings,
            self.project_directory,
        )

    def always_install(self) -> bool:
        return True


def _run_with_uv_indexes(command: list[str], settings: PythonSettings, work_dir: Path) -> None:
    """
    Inject indexes and credentials via environment variables until uv supports keyring:
    https://github.com/astral-sh/uv/issues/8810.
    """
    logger.info("Run '%s' in %s.", " ".join(command), work_dir)
    env_vars = UvIndexes.from_package_indexes(settings.package_indexes.values()).to_env()
    sp.run(command, cwd=work_dir, env={**os.environ, **env_vars}, check=True)
