import contextlib
import logging
from pathlib import Path
from typing import Any

from kraken.common import atomic_file_swap, not_none
from kraken.core import Project, Property, TaskStatus
from kraken.std.cargo import CargoProject

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

    #: Version to be bumped up to
    version: Property[str | None] = Property.default(None)

    #: Cargo.toml which to temporarily bump
    cargo_toml_file: Property[Path] = Property.default("Config.toml")

    def get_cargo_command(self, env: dict[str, str]) -> list[str]:
        super().get_cargo_command(env)
        registry = self.registry.get()
        if registry.publish_token is None:
            raise ValueError(f'registry {registry.alias!r} missing a "publish_token"')
        command = (
            ["cargo", "publish"]
            + (["--locked"] if self.should_add_locked_flag() else [])
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

    def _get_updated_cargo_toml(self, version: str) -> str:
        from kraken.std.cargo.manifest import CargoManifest

        manifest = CargoManifest.read(self.cargo_toml_file.get())
        if manifest.package is None:
            return manifest.to_toml_string()

        # Cargo does not play nicely with semver metadata (ie. 1.0.1-dev3+abc123)
        # We replace that to 1.0.1-dev3abc123
        fixed_version_string = version.replace("+", "")
        manifest.package.version = fixed_version_string
        if manifest.workspace and manifest.workspace.package:
            manifest.workspace.package.version = version

        if self.registry.is_filled():
            CargoProject.get_or_create(self.project)
            registry = self.registry.get()
            if manifest.dependencies:
                self._push_version_to_path_deps(fixed_version_string, manifest.dependencies.data, registry.alias)
            if manifest.build_dependencies:
                self._push_version_to_path_deps(fixed_version_string, manifest.build_dependencies.data, registry.alias)
        return manifest.to_toml_string()

    def _push_version_to_path_deps(
        self, version_string: str, dependencies: dict[str, Any], registry_alias: str
    ) -> None:
        """For each dependency in the given dependencies, if the dependency is a `path` dependency, injects the current
        version and registry (required for publishing - path dependencies cannot be published alone)."""
        for dep_name in dependencies:
            dependency = dependencies[dep_name]
            if isinstance(dependency, dict):
                if "path" in dependency:
                    dependency["version"] = f"={version_string}"
                    dependency["registry"] = registry_alias

    def execute(self) -> TaskStatus:
        with contextlib.ExitStack() as stack:
            if (version := self.version.get()) is not None:
                content = self._get_updated_cargo_toml(version)
                fp = stack.enter_context(atomic_file_swap(self.cargo_toml_file.get(), "w", always_revert=True))
                fp.write(content)
                fp.close()
            result = super().execute()
        return result
