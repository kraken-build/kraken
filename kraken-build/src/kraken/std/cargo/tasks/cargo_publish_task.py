import logging
from pathlib import Path

from kraken.common import not_none
from kraken.core import Project, Property

from ..config import CargoRegistry
from .cargo_build_task import CargoBuildTask

logger = logging.getLogger(__name__)


class CargoPublishTask(CargoBuildTask):
    """Publish a Cargo crate."""

    #: Path to the Cargo configuration file (defaults to `.cargo/config.toml`).
    cargo_config_file: Property[Path] = Property.default(".cargo/config.toml")

    #: Name of the package to publish (only requried for publishing packages from workspace)
    package_name: Property[str | None] = Property.default(None)

    #: The registry to publish the package to.
    registry: Property[CargoRegistry]

    #: Verify (build the crate).
    verify: Property[bool] = Property.default(True)

    #: Allow dirty worktree.
    allow_dirty: Property[bool] = Property.default(False)

    def get_cargo_command(self, env: dict[str, str]) -> list[str]:
        super().get_cargo_command(env)
        registry = self.registry.get()
        if registry.publish_token is None:
            raise ValueError(f'registry {registry.alias!r} missing a "publish_token"')
        command = (
            ["cargo", "publish"]
            + self.additional_args.get()
            + ["--registry", registry.alias, "--token", registry.publish_token]
            + ([] if self.verify.get() else ["--no-verify"])
        )
        package_name = self.package_name.get()
        if package_name is not None:
            command += ["--package", package_name]
        if self.allow_dirty.get() and "--allow-dirty" not in command:
            command.append("--allow-dirty")
        return command

    def make_safe(self, args: list[str], env: dict[str, str]) -> None:
        args[args.index(not_none(self.registry.get().publish_token))] = "[MASKED]"
        super().make_safe(args, env)

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self._base_command = ["cargo", "publish"]
