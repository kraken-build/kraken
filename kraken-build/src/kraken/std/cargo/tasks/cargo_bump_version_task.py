from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from kraken.common import atomic_file_swap
from kraken.core import BackgroundTask, Property, TaskStatus

from kraken.std.cargo import CargoProject
from kraken.std.cargo.manifest import CargoManifest


class CargoBumpVersionTask(BackgroundTask):
    """This task bumps the version numbers in `Cargo.toml`, and if a registry is specified, updates the registry and
    version of 'path' dependencies. The change can be reverted afterwards if the :attr:`revert` option is enabled."""

    description = 'Bump the version in "%(cargo_toml_file)s" to "%(version)s" [temporary: %(revert)s]'
    version: Property[str]
    registry: Property[str]
    revert: Property[bool] = Property.default(False)
    cargo_toml_file: Property[Path]

    def _get_updated_cargo_toml(self) -> str:
        manifest = CargoManifest.read(self.cargo_toml_file.get())
        if manifest.package is None:
            return manifest.to_toml_string()

        # Cargo does not play nicely with semver metadata (ie. 1.0.1-dev3+abc123)
        # We replace that to 1.0.1-dev3abc123
        fixed_version_string = self.version.get().replace("+", "")
        manifest.package.version = fixed_version_string
        if manifest.workspace and manifest.workspace.package:
            manifest.workspace.package.version = self.version.get()

        if self.registry.is_filled():
            cargo = CargoProject.get_or_create(self.project)
            registry = cargo.registries[self.registry.get()]
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

    # BackgroundTask

    def start_background_task(self, exit_stack: contextlib.ExitStack) -> TaskStatus | None:
        content = self._get_updated_cargo_toml()
        revert = self.revert.get()
        fp = exit_stack.enter_context(atomic_file_swap(self.cargo_toml_file.get(), "w", always_revert=revert))
        fp.write(content)
        fp.close()
        version = self.version.get()
        return (
            TaskStatus.started(f"temporary bump to {version}")
            if revert
            else TaskStatus.succeeded(f"permanent bump to {version}")
        )
