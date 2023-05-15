from __future__ import annotations

import dataclasses

from kraken.core import Project


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
