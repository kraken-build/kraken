"""
Experimental.

Support for Python projects managed by [UV](https://docs.astral.sh/uv/guides/projects/).
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
import logging
from os import fsdecode
import os
import shutil
import subprocess as sp
from collections.abc import Sequence
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, Annotated, Any, Iterable, MutableMapping, TypeVar
from urllib.parse import urlparse

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
T_PackageIndex = TypeVar("T_PackageIndex", bound=PackageIndex)
Safe = Annotated[T, "safe"]
Unsafe = Annotated[T, "unsafe"]


@dataclass
class PipIndex:
    url: str
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
    def of(index: PackageIndex) -> "PipIndex":
        credentials = index.credentials if isinstance(index, PythonSettings._PackageIndex) else None
        return PipIndex(index.index_url, credentials)


@dataclass
class PipIndexes:
    primary: PipIndex | None
    supplemental: list[PipIndex]

    @staticmethod
    def from_package_indexes(indexes: Iterable[T_PackageIndex]) -> "PipIndexes":
        default_index = next((idx for idx in indexes if idx.priority == PackageIndex.Priority.default), None)
        primary_index = next((idx for idx in indexes if idx.priority == PackageIndex.Priority.primary), None)
        remainder = [idx for idx in indexes if idx not in (default_index, primary_index)]

        if default_index and primary_index:
            logger.warning(
                "Cannot have 'default' and 'primary' index for a UV project. The 'primary' index (%s) will be used "
                "as the first of the 'supplemental' indexes instead.",
                primary_index.alias,
            )
            remainder.insert(0, primary_index)
            primary_index = None

        elif primary_index and not default_index:
            default_index, primary_index = primary_index, None

        return PipIndexes(
            primary=PipIndex.of(default_index) if default_index is not None else None,
            supplemental=[PipIndex.of(idx) for idx in remainder],
        )

    def to_safe_args(self) -> list[str]:
        """Create a list of arguments for UV with sensitive information masked."""

        args = []
        if self.primary is not None:
            args += ["--index-url", self.primary.safe_url]
        for index in self.supplemental:
            args += ["--extra-index-url", index.safe_url]
        return args

    def to_unsafe_args(self) -> list[str]:
        """Create a list of arguments for UV with sensitive information in plaintext."""

        args = []
        if self.primary is not None:
            args += ["--index-url", self.primary.unsafe_url]
        for index in self.supplemental:
            args += ["--extra-index-url", index.unsafe_url]
        return args

    def to_config(self, config: MutableMapping[str, Any]) -> None:
        """Inject UV configuration for indexes into a configuration."""

        if self.primary is None:
            config.pop("index-url", None)
        else:
            config["index-url"] = self.primary.url

        if not self.supplemental:
            config.pop("extra-index-url", None)
        else:
            config["extra-index-url"] = [idx.url for idx in self.supplemental]

    def to_env(self) -> dict[str, str]:
        env = {}
        if self.primary is not None:
            env["UV_INDEX_URL"] = self.primary.unsafe_url
        if self.supplemental:
            env["UV_EXTRA_INDEX_URL"] = os.pathsep.join(idx.unsafe_url for idx in self.supplemental)
        return env


class UvPyprojectHandler(PyprojectHandler):
    """Implements the PyprojectHandler interface for UV projects."""

    # TODO: Support `uv.toml` configuration file?

    # PyprojectHandler

    def get_package_indexes(self) -> list[PackageIndex]:
        """Maps the UV [`index-url`][1] and [`extra-index-url`][2] options to Kraken's concept of package indices.
        Note that UV does not support the concept of "aliases" for package indices, so instead the package index alias
        is ignored and generated automatically based on the hostname and URL hash.

        [1]: https://docs.astral.sh/uv/reference/settings/#index-url
        [2]: https://docs.astral.sh/uv/reference/settings/#extra-index-url
        """

        def gen_alias(url: str) -> str:
            hostname = urlparse(url).hostname
            assert hostname is not None, "expected hostname in package index URL"
            return f"hostname-{md5(url.encode()).hexdigest()[:5]}"

        indexes: list[PackageIndex] = []
        config: dict[str, Any] = self.raw.get("tool", {}).get("uv", {})

        if index_url := config.get("index-url"):
            indexes.append(
                PackageIndex(
                    alias=gen_alias(index_url),
                    index_url=index_url,
                    priority=PackageIndex.Priority.default,
                    verify_ssl=True,
                )
            )

        for index_url in config.get("extra-index-url", []):
            indexes.append(
                PackageIndex(
                    alias=gen_alias(index_url),
                    index_url=index_url,
                    priority=PackageIndex.Priority.supplemental,
                    verify_ssl=True,
                )
            )

        return indexes

    def set_package_indexes(self, indexes: Sequence[PackageIndex]) -> None:
        """Counterpart to [`get_package_indexes()`], check there."""

        config: dict[str, Any] = self.raw.setdefault("tool", {}).setdefault("uv", {})
        PipIndexes.from_package_indexes(indexes).to_config(config)

    def get_packages(self) -> list[PyprojectHandler.Package]:
        # TODO: Detect packages in the project.
        return []


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
        indexes = PipIndexes.from_package_indexes(settings.package_indexes.values())
        safe_command = [self.uv_bin, "lock"] + indexes.to_safe_args()
        unsafe_command = [self.uv_bin, "lock"] + indexes.to_unsafe_args()
        logger.info("Running %s in '%s'", safe_command, self.project_directory)
        sp.check_call(unsafe_command, cwd=self.project_directory)
        return TaskStatus.succeeded()

    def requires_login(self) -> bool:
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

            # We can't pass the --index-url and --extra-index-url options to UV via the pyproject-build CLI,
            # so we need to use environment variables.
            indexes = PipIndexes.from_package_indexes(settings.package_indexes.values())
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
        indexes = PipIndexes.from_package_indexes(settings.package_indexes.values())
        safe_command = [self.uv_bin, "sync"] + indexes.to_safe_args()
        unsafe_command = [self.uv_bin, "sync"] + indexes.to_unsafe_args()
        logger.info("Running %s in '%s'", safe_command, self.project_directory)
        sp.check_call(unsafe_command, cwd=self.project_directory)

    def always_install(self) -> bool:
        return True
