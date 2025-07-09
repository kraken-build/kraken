import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from kraken.common import atomic_file_swap, http, not_none
from kraken.core import Project, Property, TaskStatus
from kraken.std.cargo import CargoProject
from kraken.std.cargo.manifest import CargoManifest

from ..config import CargoRegistry
from .cargo_build_task import CargoBuildTask

logger = logging.getLogger(__name__)


class CargoPublishTask(CargoBuildTask):
    """Publish a Cargo crate."""

    #: Path to the Cargo configuration file (defaults to `.cargo/config.toml`).
    cargo_config_file: Property[Path] = Property.default(".cargo/config.toml")

    #: Name of the package to publish (only required for publishing packages from workspace)
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

    #: Allow Overwrite of existing packages
    allow_overwrite: Property[bool] = Property.default(False)

    def prepare(self) -> TaskStatus | None:
        """Checks if the crate@version already exists in the registry. If so, the task will be skipped"""
        if self.allow_overwrite.get():
            return TaskStatus.pending()

        manifest = CargoManifest.read(self.cargo_toml_file.get())
        manifest_package = manifest.package
        manifest_package_name = manifest_package.name if manifest_package is not None else None
        manifest_version = manifest_package.version if manifest_package is not None else None

        package_name = self.package_name.get() or manifest_package_name
        version = self.version.get() or manifest_version

        if not package_name:
            return TaskStatus.pending("Unable to verify package existence - unknown package name")
        if not version:
            return TaskStatus.pending("Unable to verify package existence - unknown version")

        try:
            return self._check_package_existence(package_name, version, self.registry.get())
        except Exception as e:
            logger.warn(
                "An error happened while checking for {} existence in %s, %s",
                package_name,
                self.registry.get().alias,
                e,
            )
            return TaskStatus.pending("Unable to verify package existence")

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
        manifest = CargoManifest.read(self.cargo_toml_file.get())
        if manifest.package is None:
            return manifest.to_toml_string()

        fixed_version_string = self._sanitize_version(version)
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
            if manifest.dev_dependencies:
                self._push_version_to_path_deps(fixed_version_string, manifest.dev_dependencies.data, registry.alias)
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
                    del dependency["path"]

    def execute(self) -> TaskStatus:
        with contextlib.ExitStack() as stack:
            if (version := self.version.get()) is not None:
                content = self._get_updated_cargo_toml(version)
                fp = stack.enter_context(atomic_file_swap(self.cargo_toml_file.get(), "w", always_revert=True))
                fp.write(content)
                fp.close()
            result = super().execute()
        return result

    @staticmethod
    def _sanitize_version(version: str) -> str:
        """
        Cargo does not play nicely with semver metadata (ie. 1.0.1-dev3+abc123)
        We replace that to 1.0.1-dev3abc123
        """
        return version.replace("+", "")

    @classmethod
    def _check_package_existence(cls, package_name: str, version: str, registry: CargoRegistry) -> TaskStatus | None:
        """
        Checks whether the given `package_name`@`version` is indexed in the provided `registry`.

        Checking is done by reading from the registry's index HTTP API, following the
        [Index Format](https://doc.rust-lang.org/cargo/reference/registry-index.html) documentation
        """
        if not registry.index.startswith("sparse+"):
            return TaskStatus.pending("Unable to verify package existence - Only sparse registries are supported")
        index = registry.index.removeprefix("sparse+")
        index = index.removesuffix("/")

        # >> Index authentication
        config_response = http.get(f"{index}/config.json")
        if config_response.status_code == 401:
            if registry.read_credentials is None:
                return TaskStatus.pending(
                    "Unable to verify package existence - registry requires authentication, but no credentials set"
                )
            config_response = http.get(f"{index}/config.json", auth=registry.read_credentials)
            if config_response.status_code // 100 != 2:
                logger.warn(config_response.text)
                return TaskStatus.pending(
                    "Unable to verify package existence - failed to download config.json file from registry"
                )

        # >> Index files layout
        # Reference: https://doc.rust-lang.org/cargo/reference/registry-index.html#index-files
        path = []
        if len(package_name) == 1:
            path = ["1"]
        elif len(package_name) == 2:
            path = ["2"]
        elif len(package_name) == 3:
            path = ["3", package_name.lower()[0]]
        else:
            package_name_lower = package_name.lower()
            path = [package_name_lower[0:2], package_name_lower[2:4]]

        # >> Download the index file
        index_path = "/".join(path + [package_name])
        index_response = http.get(f"{index}/{index_path}", auth=registry.read_credentials)

        if index_response.status_code in [404, 410, 451]:
            return TaskStatus.pending(f"Package {package_name} does not already exists in {registry.alias}")
        elif index_response.status_code % 200 != 0:
            logger.warn(index_response.text)
            return TaskStatus.pending("Unable to verify package existence - error when fetching package information")

        sanitized_version = cls._sanitize_version(version)

        # >> Search for relevant version in the index file
        for registry_version in index_response.text.split("\n"):
            # Index File is sometimes newline terminated
            if not registry_version:
                continue
            registry_version = cls._sanitize_version(json.loads(registry_version).get("vers", ""))
            if registry_version == sanitized_version:
                return TaskStatus.skipped(
                    f"Package {package_name} with version {version} already exists in {registry.alias}"
                )
        return TaskStatus.pending(
            f"Package {package_name} with version {version} does not already exists in {registry.alias}"
        )
