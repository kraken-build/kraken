"""
Experimental.

Support for Python projects managed by [UV](https://docs.astral.sh/uv/guides/projects/).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from os import fsdecode
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Iterable, TypeVar

from kraken.common.sanitize import sanitize_http_basic_auth
from kraken.common.toml import TomlFile
from kraken.core import TaskStatus
from kraken.std.python.pyproject import PackageIndex, PyprojectHandler
from kraken.std.python.settings import PythonSettings
from kraken.std.util.url import inject_url_credentials

from . import ManagedEnvironment, PythonBuildSystem

# "uv" is a dependency of Kraken, so we can use it's packaged version.
if TYPE_CHECKING:

    def find_uv_bin() -> str: ...

else:
    from uv.__main__ import find_uv_bin


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
            default=index.priority == index.Priority.default or index.priority == index.Priority.primary,
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


class UvPythonBuildSystem(PythonBuildSystem):
    """
    Implements Python build-system capabilities for [UV].

    [UV]: https://docs.astral.sh/uv/guides/projects/
    """

    name = "UV"

    def __init__(self, project_directory: Path, uv_bin: Path | None = None) -> None:
        self.project_directory = project_directory
        self.uv_bin = str(uv_bin or Path(fsdecode(find_uv_bin())).absolute())

    def get_pyproject_reader(self, pyproject: TomlFile) -> UvPyprojectHandler:
        return UvPyprojectHandler(pyproject)

    def supports_managed_environments(self) -> bool:
        return True

    def get_managed_environment(self) -> ManagedEnvironment:
        return UvManagedEnvironment(self.project_directory, self.uv_bin)

    def update_lockfile(self, settings: PythonSettings, pyproject: TomlFile) -> TaskStatus:
        indexes = UvIndexes.from_package_indexes(settings.package_indexes.values())
        safe_command = [self.uv_bin, "lock"] + indexes.to_safe_args()
        unsafe_command = [self.uv_bin, "lock"] + indexes.to_unsafe_args()
        logger.info("Running %s in '%s'", safe_command, self.project_directory)
        sp.check_call(unsafe_command, cwd=self.project_directory)
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

        with tempfile.TemporaryDirectory() as tempdir:
            env: dict[str, str] = {}

            # Make sure that UV is on the path for `pyproject-build` to find it.
            assert Path(self.uv_bin).name == "uv"
            if shutil.which("uv") != self.uv_bin:
                env["PATH"] = str(Path(self.uv_bin).parent) + os.pathsep + env["PATH"]

            # We can't pass the --default-index and --index options to UV via the pyproject-build CLI,
            # so we need to use environment variables.
            indexes = UvIndexes.from_package_indexes(settings.package_indexes.values())
            env.update(indexes.to_env())

            command = [
                self.uv_bin,
                "tool",
                "run",
                "--from",
                "build>=1.0.0,<2.0.0",
                "pyproject-build",
                "-v",
                "--outdir",
                tempdir,
                "--installer",
                "uv",
            ]
            logger.info(
                "Running %s in '%s' with env %s",
                command,
                self.project_directory,
                sanitize_http_basic_auth(str(env)),
            )
            sp.check_call(command, cwd=self.project_directory, env={**os.environ, **env})

            src_files = list(Path(tempdir).iterdir())
            dst_files = [output_directory / path.name for path in src_files]
            for src, dst in zip(src_files, dst_files):
                shutil.move(str(src), dst)

        return dst_files

    def get_lockfile(self) -> Path | None:
        return self.project_directory / "uv.lock"


class UvManagedEnvironment(ManagedEnvironment):
    def __init__(self, project_directory: Path, uv_bin: str) -> None:
        self.project_directory = project_directory
        self.uv_bin = uv_bin
        self.env_path = project_directory / ".venv"

    # ManagedEnvironment

    def exists(self) -> bool:
        return self.env_path.is_dir()

    def get_path(self) -> Path:
        return self.env_path

    def install(self, settings: PythonSettings) -> None:
        indexes = UvIndexes.from_package_indexes(settings.package_indexes.values())
        safe_command = [self.uv_bin, "sync"] + indexes.to_safe_args()
        unsafe_command = [self.uv_bin, "sync"] + indexes.to_unsafe_args()
        logger.info("Running %s in '%s'", safe_command, self.project_directory)
        sp.check_call(unsafe_command, cwd=self.project_directory)

    def always_install(self) -> bool:
        return True
