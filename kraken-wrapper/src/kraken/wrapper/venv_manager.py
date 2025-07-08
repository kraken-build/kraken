from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlparse

from kraken.common import (
    EnvironmentType,
    LocalRequirement,
    NotSet,
    RequirementSpec,
    datetime_to_iso8601,
    findpython,
    iso8601_to_datetime,
    not_none,
    safe_rmpath,
)
from kraken.common._generic import flatten
from kraken.std.util.url import inject_url_credentials
from kraken.wrapper.uv_venv import UvVirtualEnv

from ._config import AuthModel

logger = logging.getLogger(__name__)

KRAKEN_MAIN_IMPORT_SNIPPET = "from kraken.core.cli.main import main"  # >= 0.9.0


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


@dataclasses.dataclass(frozen=True)
class VirtualEnvMetadata:
    created_at: datetime.datetime
    requirements_hash: str
    hash_algorithm: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> VirtualEnvMetadata:
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
            # For backwards compatibility <0.45.0
            "environment_type": EnvironmentType.UV.name,
        }

    @dataclasses.dataclass
    class Store:
        path: Path

        def __post_init__(self) -> None:
            self._metadata: VirtualEnvMetadata | None | NotSet = NotSet.Value

        def get(self) -> VirtualEnvMetadata | None:
            if self._metadata is NotSet.Value:
                if self.path.is_file():
                    self._metadata = VirtualEnvMetadata.from_json(json.loads(self.path.read_text()))
                else:
                    self._metadata = None
            return self._metadata

        def set(self, metadata: VirtualEnvMetadata) -> None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(metadata.to_json()))
            self._metadata = metadata


class VirtualEnvError(Exception):
    """
    An error occurred while building the environment.
    """


class VirtualEnvManager:
    def __init__(
        self,
        project_root: Path,
        path: Path,
        auth: AuthModel,
        default_type: EnvironmentType = EnvironmentType.UV,
        default_hash_algorithm: str = "sha256",
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
        self._venv = UvVirtualEnv(path)
        self._auth = auth
        self._metadata_store = VirtualEnvMetadata.Store(path.parent / (path.name + ".meta"))
        self._default_type = default_type
        self._default_hash_algorithm = default_hash_algorithm

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
        return self._venv.exists()

    def remove(self) -> None:
        self._venv.remove()
        safe_rmpath(self._metadata_store.path)

    def get_lockfile(self, requirements: RequirementSpec) -> Lockfile:
        return Lockfile(requirements=requirements, pinned={dist.name: dist.version for dist in self._venv.freeze()})

    def install(self, requirements: RequirementSpec, reinstall: bool) -> None:
        """
        Ensure that the virtual environment managed by this instance conforms to the specified requirements.

        The environment may be re-created if it is found to be in an unrecoverable state (e.g. if the interpreter
        version constraint is no longer satisfied or the environment is entirely broken).
        """

        # Inject credentials into the requirements.
        requirements = RequirementSpec(
            requirements=requirements.requirements,
            index_url=self._inject_auth(requirements.index_url) if requirements.index_url else None,
            extra_index_urls=tuple(self._inject_auth(url) for url in requirements.extra_index_urls),
            interpreter_constraint=requirements.interpreter_constraint,
            pythonpath=requirements.pythonpath,
        )

        if requirements.interpreter_constraint and (current_version := self._venv.try_version()):
            # If we have a constraint on the interpreter version we can use, check whether the current version
            # satisfies that constraint. Otherwise, we need to re-initialize the virtual env.

            if not findpython.match_version_constraint(requirements.interpreter_constraint, current_version):
                logger.info(
                    "Existing environment at %s does not match constraint %s because its Python version "
                    "is %s. The environment will be recreated with the correct interpreter.",
                    self._path,
                    requirements.interpreter_constraint,
                    current_version,
                )
                safe_rmpath(self._path)

        if self._venv.exists() and not self._venv.is_success_marker_set():
            logger.warning("Your virtual build environment appears to be corrupt. It will be recreated. This happens")
            logger.warning("by pressing Ctrl+C during its installation, or if you've recently upgraded kraken-wrapper.")
            safe_rmpath(self._path)

        if reinstall and self._venv.exists():
            logger.debug("Destroying existing virtual environment at %s", self._path)
            self._venv.remove()

        if self._venv.exists():
            logger.info("Reusing virtual environment at %s", self._path)
        else:
            # If the virtual env does not exist, we need to create it. For that we first need to find a Python version
            # that matches our interpreter constraint. If we have no constraint, might as well use the version of
            # Python we're currently running with.

            if requirements.interpreter_constraint is not None:
                logger.debug("Using Python interpreter constraint: %s", requirements.interpreter_constraint)
                original_python = find_python_interpreter(requirements.interpreter_constraint)
                logger.debug("Using Python interpreter at %s", original_python)
            else:
                logger.info(
                    "No interpreter constraint specified, using current Python interpreter (%s)",
                    sys.executable,
                )
                original_python = sys.executable

            self._venv.create(python=Path(original_python))

        if requirements.requirements:
            self._venv.install(
                requirements=flatten(req.to_args(self._project_root) for req in requirements.requirements),
                index_url=requirements.index_url,
                extra_index_urls=requirements.extra_index_urls,
            )
        else:
            logger.info("No requirements specified, skipping install step.")

        self._venv.install_pth_file("krakenw.pth", list(requirements.pythonpath))
        self._venv.set_success_marker(True)

        # Update our stored environment metadata.
        hash_algorithm = self.get_hash_algorithm()
        metadata = VirtualEnvMetadata(
            datetime.datetime.now(datetime.timezone.utc),
            requirements.to_hash(hash_algorithm),
            hash_algorithm,
        )
        self._metadata_store.set(metadata)

    def get_metadata_file(self) -> Path:
        return self._metadata_store.path

    def get_metadata(self) -> VirtualEnvMetadata:
        return not_none(self._metadata_store.get(), "metadata does not exist")

    def get_hash_algorithm(self) -> str:
        metadata = self._metadata_store.get()
        return metadata.hash_algorithm if metadata else self._default_hash_algorithm

    def set_locked(self, lockfile: Lockfile) -> None:
        metadata = self._metadata_store.get()
        assert metadata is not None
        metadata = VirtualEnvMetadata(
            metadata.created_at,
            lockfile.to_pinned_requirement_spec().to_hash(metadata.hash_algorithm),
            metadata.hash_algorithm,
        )
        self._metadata_store.set(metadata)

    def dispatch_to_kraken_cli(self, argv: list[str]) -> NoReturn:
        python = self._venv.python_bin
        command = [str(python), "-c", f"{KRAKEN_MAIN_IMPORT_SNIPPET}\nmain()", *argv]

        env = os.environ.copy()
        self._venv.activate(env)

        # We only support UV environments from v0.45.0.
        EnvironmentType.UV.set(env)

        sys.exit(subprocess.call(command, env=env))


@dataclasses.dataclass
class Lockfile:
    """
    A Kraken lock file encodes the original requirements that were used to resolve and install a virtual environment
    and contains the pinned requirements so the exact environment can be reproduced.
    """

    requirements: RequirementSpec
    pinned: dict[str, str]

    @staticmethod
    def from_path(path: Path) -> Lockfile:
        import tomli

        with path.open("rb") as fp:
            return Lockfile.from_json(tomli.load(fp))

    def write_to(self, path: Path) -> None:
        import tomli_w

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fp:
            tomli_w.dump(self.to_json(), fp)

    @staticmethod
    def from_json(data: dict[str, Any]) -> Lockfile:
        return Lockfile(
            requirements=RequirementSpec.from_json(data["requirements"]),
            pinned=data["pinned"],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "requirements": self.requirements.to_json(),
            "pinned": self.pinned,
        }

    def to_pinned_requirement_spec(self) -> RequirementSpec:
        """Converts the pinned versions in the lock file to a :class:`RequirementSpec` with the pinned requirements."""

        requirements = RequirementSpec(
            requirements=(),
            index_url=self.requirements.index_url,
            extra_index_urls=self.requirements.extra_index_urls[:],
            pythonpath=self.requirements.pythonpath[:],
            interpreter_constraint=self.requirements.interpreter_constraint,
        )

        # Make sure that local requirements keep being installed from the local source.
        local_requirements = {
            dep.name: dep for dep in self.requirements.requirements if isinstance(dep, LocalRequirement)
        }
        requirements = requirements.with_requirements(local_requirements.values())

        # Add all non-local requirements with exact version numbers.
        requirements = requirements.with_requirements(
            f"{key}=={value}" for key, value in sorted(self.pinned.items()) if key not in local_requirements
        )

        return requirements
