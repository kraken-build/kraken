from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import logging
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from contextlib import ExitStack
from os import fsdecode
from pathlib import Path
from typing import Any, Literal, NoReturn
from urllib.parse import urlparse

from uv.__main__ import find_uv_bin

from kraken.common import (
    EnvironmentType,
    NotSet,
    RequirementSpec,
    datetime_to_iso8601,
    findpython,
    iso8601_to_datetime,
    not_none,
    safe_rmpath,
)
from kraken.common.pyenv import VirtualEnvInfo
from kraken.common.sanitize import sanitize_http_basic_auth
from kraken.std.util.url import inject_url_credentials

from ._config import AuthModel
from ._lockfile import Distribution, Lockfile

logger = logging.getLogger(__name__)

KRAKEN_MAIN_IMPORT_SNIPPET = """
try:
    from kraken.core.cli.main import main  # >= 0.9.0
except ImportError:
    from kraken.cli.main import main  # < 0.9.0
""".strip()


@dataclasses.dataclass(frozen=True)
class BuildEnvMetadata:
    created_at: datetime.datetime
    requirements_hash: str
    hash_algorithm: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BuildEnvMetadata:
        return cls(
            created_at=iso8601_to_datetime(data["created_at"]),
            requirements_hash=data["requirements_hash"],
            hash_algorithm=data["hash_algorithm"],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "created_at": datetime_to_iso8601(self.created_at),
            "requirements_hash": self.requirements_hash,
            "hash_algorithm": self.hash_algorithm,
        }


@dataclasses.dataclass
class BuildEnvMetadataStore:
    path: Path

    def __post_init__(self) -> None:
        self._metadata: BuildEnvMetadata | None | NotSet = NotSet.Value

    def get(self) -> BuildEnvMetadata | None:
        if self._metadata is NotSet.Value:
            if self.path.is_file():
                self._metadata = BuildEnvMetadata.from_json(json.loads(self.path.read_text()))
            else:
                self._metadata = None
        return self._metadata

    def set(self, metadata: BuildEnvMetadata) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(metadata.to_json()))
        self._metadata = metadata


class BuildEnvError(Exception):
    """
    An error occurred while building the environment.
    """


def general_get_installed_distributions(kraken_command_prefix: Sequence[str]) -> list[Distribution]:
    command = [*kraken_command_prefix, "query", "env"]
    output = subprocess.check_output(command).decode()
    return [Distribution(x["name"], x["version"], x["requirements"], x["extras"]) for x in json.loads(output)]


def find_python_interpreter(constraint: str) -> str:
    """
    Finds a Python interpreter that matches the given constraint. We rely on the order of candidates returned by
    #findpython.get_candidates() and return the first matching Python version.
    """

    interpreters = findpython.evaluate_candidates(findpython.get_candidates(), findpython.InterpreterVersionCache())
    for interpreter in interpreters:
        if findpython.match_version_constraint(constraint, interpreter["version"]):
            return interpreter["path"]

    raise RuntimeError(f"Could not find a Python interpreter that matches the constraint {constraint!r}.")


class BuildEnv:
    """
    Handles the creation and updating of a Python virtual environment using the Uv package manager for the purpose
    of executing the Kraken build tool.
    """

    def __init__(self, project_root: Path, path: Path, incremental: bool = False, show_pip_logs: bool = False) -> None:
        """
        Args:
            project_root: Path for resolving relative local requirements.
            path: Path where the virtual env will be created.
            incremental: Whether install operations can re-use an existing state of the virtual environment.
            show_pip_logs: Keep Pip logs attached to the terminal. Otherwise they're piped to a file.
        """

        self._project_root = project_root
        self._path = path
        self._venv = VirtualEnvInfo(self._path)
        self._incremental = incremental
        self._show_pip_logs = show_pip_logs
        self._uv_bin = fsdecode(find_uv_bin())

    def _get_create_venv_command(self, python_bin: Path, path: Path) -> list[str]:
        return [self._uv_bin, "venv", str(path)]

    def _get_install_command(self, venv_dir: Path, requirements: RequirementSpec, env: dict[str, str]) -> list[str]:
        env["VIRTUAL_ENV"] = str(venv_dir)
        return [self._uv_bin, "pip", "install", "--no-config", *requirements.to_args(base_dir=self._project_root)]

    def _run_command(
        self,
        command: list[str],
        operation_name: str,
        log_file: Path | None,
        mode: Literal["a", "w"] = "w",
        env: dict[str, str] | None = None,
    ) -> None:
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)

        offset: int | None = None
        exc: Exception | None = None

        with ExitStack() as stack:
            if log_file is not None:
                fp = stack.enter_context(log_file.open(mode))
                offset = fp.tell()
            else:
                fp = None
                offset = 0
            try:
                subprocess.check_call(command, stdout=fp, stderr=fp, env=env)
                return
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                exc = e

        assert exc is not None
        exit_code = exc.returncode if isinstance(exc, subprocess.CalledProcessError) else -1
        command_str = "$ " + " ".join(map(shlex.quote, command))
        command_str = sanitize_http_basic_auth(command_str)

        if log_file:
            assert offset is not None
            with log_file.open() as fp:
                fp.seek(offset)
                logger.error(
                    "'%s' failed (exit code: %d, command: %s). Output:\n\n%s",
                    operation_name,
                    exit_code,
                    command_str,
                    fp.read(),
                )
        else:
            logger.error(
                "'%s' failed (exit code: %d, command: %s). Check the output above for more information.",
                operation_name,
                exc.returncode if isinstance(exc, subprocess.CalledProcessError) else -1,
                command_str,
            )

        raise BuildEnvError(f"The command failed: {command_str}") from exc

    def _install_pythonpath(self, venv_dir: Path, pythonpath: list[str]) -> None:
        """Install the given pythonpath into the virtual environment."""
        python_bin = venv_dir / "bin" / "python"
        command = [str(python_bin), "-c", "from sysconfig import get_path; print(get_path('purelib'))"]
        site_packages = Path(subprocess.check_output(command).decode().strip())
        pth_file = site_packages / "krakenw.pth"
        if pythonpath:
            logger.debug("Writing .pth file at %s", pth_file)
            pth_file.write_text("\n".join(str(Path(path).absolute()) for path in pythonpath))
        elif pth_file.is_file():
            logger.debug("Removing .pth file at %s", pth_file)
            pth_file.unlink()

    def get_path(self) -> Path:
        return self._path

    def get_installed_distributions(self) -> list[Distribution]:
        python = self._venv.get_bin("python")
        return general_get_installed_distributions([str(python), "-c", f"{KRAKEN_MAIN_IMPORT_SNIPPET}\nmain()"])

    def build(self, requirements: RequirementSpec, transitive: bool) -> None:
        if self._show_pip_logs:
            create_log: Path | None = self._path.with_name(self._path.name + ".log") / "create.txt"
            install_log: Path | None = self._path.with_name(self._path.name + ".log") / "install.txt"
        else:
            create_log = install_log = None

        if not self._incremental and self._path.exists():
            logger.debug("Removing existing virtual environment at %s", self._path)
            safe_rmpath(self._path)

        python_bin = str(self._venv.get_bin("python"))
        success_flag = self._path / ".success.flag"

        # If a virtual environment already exists, we should ensure that it matches the given interpreter constraint.
        if os.path.isfile(python_bin) and success_flag.is_file():
            try:
                current_python_version = findpython.get_python_interpreter_version(python_bin)
            except (subprocess.CalledProcessError, RuntimeError) as e:
                logger.warning("Could not determine the version of the current Python build environment: %s", e)
                logger.info("Destroying existing environment at %s", self._path)
                safe_rmpath(self._path)
            else:
                if requirements.interpreter_constraint and not findpython.match_version_constraint(
                    requirements.interpreter_constraint, current_python_version
                ):
                    logger.info(
                        "Existing Python interpreter at %s does not match constraint %s because its Python version "
                        "is %s. The environment will be recreated with the correct interpreter.",
                        python_bin,
                        requirements.interpreter_constraint,
                        current_python_version,
                    )
                    safe_rmpath(self._path)

        elif self._venv.exists() and not success_flag.is_file():
            logger.warning("Your virtual build environment appears to be corrupt. It will be recreated. This happens")
            logger.warning("by pressing Ctrl+C during its installation, or if you've recently upgraded kraken-wrapper.")
            safe_rmpath(self._path)

        if not self._path.exists():
            # Find a Python interpreter that matches the given interpreter constraint.
            if requirements.interpreter_constraint is not None:
                logger.info("Using Python interpreter constraint: %s", requirements.interpreter_constraint)
                python_origin_bin = find_python_interpreter(requirements.interpreter_constraint)
                logger.info("Using Python interpreter at %s", python_origin_bin)
            else:
                logger.info(
                    "No interpreter constraint specified, using current Python interpreter (%s)", sys.executable
                )
                python_origin_bin = sys.executable

            command = self._get_create_venv_command(Path(python_origin_bin), self._path)
            logger.info("Creating virtual environment at %s", os.path.relpath(self._path))
            self._run_command(command, operation_name="Create virtual environment", log_file=create_log)
            success_flag.touch()

        else:
            logger.info("Reusing virtual environment at %s", self._path)

        # Install requirements.
        if not requirements.requirements:
            logger.info("No requirements specified, skipping install step.")
        else:
            env = os.environ.copy()
            command = self._get_install_command(self._path, requirements, env)
            logger.info("Installing dependencies.")
            logger.debug("Installing into build environment with uv: %s", sanitize_http_basic_auth(" ".join(command)))
            self._run_command(command, operation_name="Install dependencies", log_file=install_log, env=env)

        # Make sure the pythonpath from the requirements is encoded into the environment.
        self._install_pythonpath(self._path, list(requirements.pythonpath))

    def dispatch_to_kraken_cli(self, argv: list[str]) -> NoReturn:
        python = self._venv.get_bin("python")
        command = [str(python), "-c", f"{KRAKEN_MAIN_IMPORT_SNIPPET}\nmain()", *argv]

        env = os.environ.copy()
        # We only support UV environments from v0.45.0.
        EnvironmentType.UV.set(env)
        env["PATH"] = str(self._venv.get_bin_directory()) + os.pathsep + env.get("PATH", "")

        sys.exit(subprocess.call(command, env=env))


class BuildEnvManager:
    def __init__(
        self,
        project_root: Path,
        path: Path,
        auth: AuthModel,
        default_type: EnvironmentType = EnvironmentType.UV,
        default_hash_algorithm: str = "sha256",
        incremental: bool = False,
        show_install_logs: bool = False,
    ) -> None:
        """
        Args:
            project_root: Path for resolving relative local requirements.
            path: Path to the directory that contains the build environment (virtual env).
        """

        assert (
            default_hash_algorithm in hashlib.algorithms_available
        ), f"hash algorithm {default_hash_algorithm!r} is not available"

        self._project_root = project_root
        self._path = path
        self._auth = auth
        self._metadata_store = BuildEnvMetadataStore(path.parent / (path.name + ".meta"))
        self._default_type = default_type
        self._default_hash_algorithm = default_hash_algorithm
        self._incremental = incremental
        self._show_install_logs = show_install_logs

    def _inject_auth(self, url: str) -> str:
        parsed_url = urlparse(url)
        credentials = self._auth.get_credentials(parsed_url.netloc)
        if credentials is None:
            return url

        logger.info('Injecting username and password into index url "%s"', url)
        return inject_url_credentials(url, *credentials)

    def exists(self) -> bool:
        if self._metadata_store.get() is None:
            return False  # If we don't have metadata, we assume the environment does not exist.
        return self.get_environment().get_path().exists()

    def remove(self) -> None:
        safe_rmpath(self._metadata_store.path)
        safe_rmpath(self.get_environment().get_path())

    def install(
        self,
        requirements: RequirementSpec,
        transitive: bool = True,
        allow_incremental: bool = True,
    ) -> None:
        """
        Args:
            requirements: The requirements to build the environment with.
            transitive: If set to `False`, it indicates that the *requirements* are fully resolved and the
                        build environment installer does not need to resolve transitve dependencies.
            allow_incremental: Allow incremental builds if the environment already exists. Set to False if
                               the environment type changes.
        """

        # Inject credentials into the requirements.
        requirements = RequirementSpec(
            requirements=requirements.requirements,
            index_url=self._inject_auth(requirements.index_url) if requirements.index_url else None,
            extra_index_urls=tuple(self._inject_auth(url) for url in requirements.extra_index_urls),
            interpreter_constraint=requirements.interpreter_constraint,
            pythonpath=requirements.pythonpath,
        )

        env = self.get_environment(allow_incremental)
        env.build(requirements, transitive)
        hash_algorithm = self.get_hash_algorithm()
        metadata = BuildEnvMetadata(
            datetime.datetime.now(datetime.timezone.utc),
            requirements.to_hash(hash_algorithm),
            hash_algorithm,
        )
        self._metadata_store.set(metadata)

    def get_metadata_file(self) -> Path:
        return self._metadata_store.path

    def get_metadata(self) -> BuildEnvMetadata:
        return not_none(self._metadata_store.get(), "metadata does not exist")

    def get_hash_algorithm(self) -> str:
        metadata = self._metadata_store.get()
        return metadata.hash_algorithm if metadata else self._default_hash_algorithm

    def get_environment(self, allow_incremental: bool = True) -> BuildEnv:
        return BuildEnv(
            project_root=self._project_root,
            path=self._path,
            incremental=self._incremental and allow_incremental,
            show_pip_logs=self._show_install_logs,
        )

    def set_locked(self, lockfile: Lockfile) -> None:
        metadata = self._metadata_store.get()
        assert metadata is not None
        metadata = BuildEnvMetadata(
            metadata.created_at,
            lockfile.to_pinned_requirement_spec().to_hash(metadata.hash_algorithm),
            metadata.hash_algorithm,
        )
        self._metadata_store.set(metadata)
