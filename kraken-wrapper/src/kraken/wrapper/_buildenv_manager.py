from __future__ import annotations

import datetime
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

from kraken.common import EnvironmentType, RequirementSpec, not_none, safe_rmpath
from kraken.std.util.url import inject_url_credentials

from ._buildenv import BuildEnv, BuildEnvMetadata, BuildEnvMetadataStore
from ._buildenv_uv import UvBuildEnv
from ._config import AuthModel
from ._lockfile import Lockfile

logger = logging.getLogger(__name__)


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
        return UvBuildEnv(
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
