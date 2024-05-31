from __future__ import annotations

import dataclasses
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from kraken.common import atomic_file_swap
from kraken.core import Project

from .manifest import CargoManifest


@dataclasses.dataclass
class CargoRegistry:
    """Represents a Cargo registry."""

    #: The registrt alias. This is used as an identifier when publishing the registry and when referencing a crate
    #: from the registry in the `Cargo.toml` dependencies.
    alias: str

    #: The URL of the Cargo registry index. This usually points to a Git repository, as that is how Cargo registries
    #: are stored. The index URL must be present in `.cargo/config.toml` for Cargo to consume crates from it.
    index: str

    #: Authentication credentials for reading from the registry. This is only needed if the registry is private and the
    #: index URL is an HTTP(S) URL. The credentials will be passed using HTTP Basic authentication.
    read_credentials: tuple[str, str] | None = None

    #: The publish token for this registry.
    publish_token: str | None = None


@dataclasses.dataclass
class CargoProject:
    """Container for all Cargo related settings that can be automatically managed from a Kraken build."""

    #: The registries for the Cargo project. We store the registrie's by their alias.
    registries: dict[str, CargoRegistry] = dataclasses.field(default_factory=dict)

    #: Environment variables for cargo build steps.
    build_env: dict[str, str] = dataclasses.field(default_factory=dict)

    def add_registry(
        self,
        alias: str,
        index: str,
        read_credentials: tuple[str, str] | None = None,
        publish_token: str | None = None,
    ) -> None:
        """Add a registry to the project.

        :param alias: The alias of the registry. This alias is used in` Cargo.toml` to describe which registry to look
            up a create in. It is also used to designate the registry to publish to in `cargo publish`.
        :param index: The registry index URL.
        :param read_credentials: A `(username, password)` tuple for reading from the repository (optional).
        :param publish_token: A token to publish to the repository (optional).
        """

        self.registries[alias] = CargoRegistry(alias, index, read_credentials, publish_token)

    @staticmethod
    def get_or_create(project: Project | None) -> CargoProject:
        project = project or Project.current()
        return project.find_metadata(CargoProject, CargoProject)


@dataclasses.dataclass
class CargoConfig:
    nightly: bool


class CargoManifestManager:
    """
    This is a helper class to perform changes to a `Cargo.toml` configuration file, sometimes only temporarily.
    For example to bumping the version of a project at build and publish time.

    Example usage:

    ```py
    with CargoConfigManager() as cfg:
        cfg.set_version("1.0.0", "crates.io")
        cfg.write()
        build_cargo_project()
    ```
    """

    def __init__(self, cargo_toml: Path) -> None:
        self._cargo_toml = cargo_toml
        self._stack = ExitStack()
        self._config_backed_up = False
        self._manifest: CargoManifest | None = None

    def __enter__(self) -> CargoManifestManager:
        self._stack.__enter__()
        return self

    def __exit__(self, *a: Any) -> None | bool:
        return self._stack.__exit__(*a)

    @property
    def manifest(self) -> CargoManifest:
        if self._manifest is None:
            self._manifest = CargoManifest.read(self._cargo_toml)
        return self._manifest

    def set_version(self, version: str, registry_alias: str | None = None) -> None:
        """
        Updates the `version` field in the `[project]` section of the `Cargo.toml`.

        If any path dependencies are found in the manifest, they are assumed to be have been published to the given
        *registry_alias* with the same *version* and are translated to registry dependencies.
        """

        manifest = self.manifest
        if not manifest.package:
            return

        # Cargo does not play nicely with semver metadata (ie. 1.0.1-dev3+abc123)
        # We replace that to 1.0.1-dev3abc123
        fixed_version_string = version.replace("+", "")
        manifest.package.version = fixed_version_string
        if manifest.workspace and manifest.workspace.package:
            manifest.workspace.package.version = version

        def update_path_deps(dependencies: dict[str, Any]) -> None:
            for dep_name in dependencies:
                dependency = dependencies[dep_name]
                if isinstance(dependency, dict):
                    if "path" in dependency:
                        dependency["version"] = f"={fixed_version_string}"
                        dependency["registry"] = registry_alias

        # CargoProject.get_or_create(None)
        if registry_alias is not None:
            if manifest.dependencies:
                update_path_deps(manifest.dependencies.data)
            if manifest.build_dependencies:
                update_path_deps(manifest.build_dependencies.data)

    def write(self) -> None:
        fp = self._stack.enter_context(atomic_file_swap(self._cargo_toml, "w", always_revert=True))
        fp.write(self.manifest.to_toml_string())
        fp.close()
