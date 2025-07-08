"""Implements Maturin as a build system for kraken-std."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
import warnings
from collections.abc import Collection
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from kraken.common.path import is_relative_to
from kraken.common.toml import TomlFile

from ...cargo.manifest import CargoMetadata
from ..pyproject import PyprojectHandler
from ..settings import PythonSettings
from . import ManagedEnvironment, PythonBuildSystem
from .pdm import PDMManagedEnvironment, PDMPythonBuildSystem
from .poetry import PoetryManagedEnvironment, PoetryPyprojectHandler, PoetryPythonBuildSystem
from .uv import UvPythonBuildSystem

logger = logging.getLogger(__name__)


@dataclass
class MaturinZigTarget:
    """A specific target to build for with Maturin.
    :param target: Rust target to cross-compile to using zig.
        For example "x86_64-unknown-linux-gnu" or "aarch64-apple-darwin".
        Requires the `maturin[zig]` pip package.
        These targets should be installed into the Rust installation.
    :param zig_features: Cargo features to enable for zig builds. If zig is used, it should be at least `pyo3/abi3`
        or another feature depending on `pyo3/abi3` (`pyo3/abi3-py38`...).
    :param manylinux: if set to true, this will produce a manylinux wheel, and any dynamically
        linked libraries will be copied into the wheel. If false, wheels will be tagged as
        'linux' and dynamically linked libraries are the responsibility of the user.
    :param macos_sdk_root: For zig builds targeting macOS, the path to the MacOS SDK to use.
        By default, the `SDKROOT` environment variable is used as a fallback.
        Only required when cross compiling from Linux to MacOS.
    :param rustflags: RUSTFLAGS environment variable will be set at compilation time. This can be
        used to add e.g. native libraries to link against.
    :param ld_library_path: LD_LIBRARY_PATH environment variable will be set at compilation time. This can be
        used to add any native libraries that might be required by pypa fixups so to produce manylinux wheels.
        Likely the same content as RUSTFLAGS, but in the LD_LIBRARY_PATH format.
    """

    target: str
    rustflags: str | None = None
    ld_library_path: str | None = None
    macos_sdk_root: Path | None = None
    manylinux: bool = True
    zig_features: Collection[str] = ()


class _MaturinBuilder:
    def __init__(self, entry_point: Collection[str], build_system: PythonBuildSystem) -> None:
        self._entry_point = entry_point
        self._build_system = build_system
        self._default_build = True
        self._zig_targets: Collection[MaturinZigTarget] = []
        self._build_env: dict[str, str] = {}

    def disable_default_build(self) -> None:
        self._default_build = False

    def enable_zig_build(self, targets: Collection[MaturinZigTarget]) -> None:
        """
        :param targets: Collection of MaturinTargets to cross-compile to using zig.
        """
        self._zig_targets = targets

    def add_build_environment_variable(self, key: str, value: str) -> None:
        self._build_env[key] = value

    def build(self, output_directory: Path) -> list[Path]:
        # We clean up target dir
        metadata = CargoMetadata.read(self._build_system.project_directory)
        dist_dir = metadata.target_directory / "wheels"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        # We run the actual build
        build_env = {**os.environ, **self._build_env}
        if self._default_build:
            command = [*self._entry_point, "maturin", "build", "--release"]
            logger.info("%s", command)
            sp.check_call(command, cwd=self._build_system.project_directory, env=build_env)
        for target in self._zig_targets:
            command = [
                *self._entry_point,
                "maturin",
                "build",
                "--release",
                "--zig",
                "--target",
                target.target,
                "--features",
                ",".join(target.zig_features),
                "--interpreter",
                str(self._build_system.get_managed_environment().get_path() / "bin" / "python"),
            ]
            if not target.manylinux:
                command.append("--manylinux")
                command.append("off")
            logger.info("%s", command)
            target_build_env = build_env.copy()
            if target.target.endswith("-apple-darwin"):
                if target.macos_sdk_root is not None:
                    target_build_env["SDKROOT"] = str(target.macos_sdk_root.resolve())
                elif "SDKROOT" not in target_build_env:
                    logger.error(f"No macOS SDKROOT set for the target {target}")
            if target.rustflags is not None:
                target_build_env["RUSTFLAGS"] = target.rustflags
            if target.ld_library_path is not None:
                target_build_env["LD_LIBRARY_PATH"] = target.ld_library_path
            sp.check_call(command, cwd=self._build_system.project_directory, env=target_build_env)

        # We get the output files
        src_files = list(dist_dir.iterdir())
        dst_files = [output_directory / path.name for path in src_files]
        for src, dst in zip(src_files, dst_files, strict=True):
            shutil.move(str(src), dst)

        # Unless the output directory is a subdirectory of the dist_dir, we remove the dist dir again.
        if not is_relative_to(output_directory, dist_dir):
            shutil.rmtree(dist_dir)

        return dst_files


class MaturinPoetryPyprojectHandler(PoetryPyprojectHandler):
    def set_version(self, version: str | None) -> None:
        PyprojectHandler.set_version(self, version)
        PoetryPyprojectHandler.set_version(self, version)

    def synchronize_project_section_to_poetry_state(self) -> None:
        """
        Synchronize the `[tool.poetry]` package metadata to the `[project]` section.

        In the case where only the `[project]` section exists, we sync it into the other direction.
        """

        poetry_section = self._poetry_section
        project_section = self.raw.setdefault("project", {})
        for field_name in ("name", "version"):
            poetry_value = poetry_section.get(field_name)
            project_value = project_section.get(field_name)
            if poetry_value is None:
                poetry_section[field_name] = project_value
            else:
                project_section[field_name] = poetry_value


class MaturinPoetryPythonBuildSystem(PoetryPythonBuildSystem):
    """A maturin-backed version of the Poetry build system, that invokes the maturin build-backend.
    Can be enabled by adding the following to the local pyproject.yaml:
    ```toml
    [tool.poetry.group.dev.dependencies]
    maturin = "^1.0"

    [build-system]
    requires = ["maturin~=1.0"]
    build-backend = "maturin"
    ```
    """

    name = "Maturin Poetry"

    def __init__(self, project_directory: Path) -> None:
        super().__init__(project_directory)
        self._builder = _MaturinBuilder(["poetry", "run"], self)

    def disable_default_build(self) -> None:
        self._builder.disable_default_build()

    def enable_zig_build(self, targets: Collection[MaturinZigTarget]) -> None:
        """
        :param targets: Collection of MaturinTargets to cross-compile to using zig.
        """
        self._builder.enable_zig_build(targets)

    def add_build_environment_variable(self, key: str, value: str) -> None:
        self._builder.add_build_environment_variable(key, value)

    # PythonBuildSystem

    def get_pyproject_reader(self, pyproject: TomlFile) -> MaturinPoetryPyprojectHandler:
        return MaturinPoetryPyprojectHandler(pyproject)

    def get_managed_environment(self) -> ManagedEnvironment:
        return MaturinPoetryManagedEnvironment(self.project_directory)

    def update_pyproject(self, settings: PythonSettings, pyproject: TomlFile) -> None:
        super().update_pyproject(settings, pyproject)
        handler = self.get_pyproject_reader(pyproject)
        handler.synchronize_project_section_to_poetry_state()

    def build(self, output_directory: Path) -> list[Path]:
        return self._builder.build(output_directory)


class MaturinPoetryManagedEnvironment(PoetryManagedEnvironment):
    def install(self, settings: PythonSettings) -> None:
        super().install(settings)
        command = ["poetry", "run", "maturin", "develop"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory)

    def always_install(self) -> bool:
        return True


class MaturinPdmPythonBuildSystem(PDMPythonBuildSystem):
    """A maturin-backed version of the PDM build system, that invokes the maturin build-backend.
    Can be enabled by adding the following to the local pyproject.yaml:
    ```toml
    [tool.pdm.dev-dependencies]
    build = ["maturin~=1.0", "pip~=23.0"]

    [build-system]
    requires = ["maturin~=1.0"]
    build-backend = "maturin"
    ```
    """

    name = "Maturin PDM"

    def __init__(self, project_directory: Path) -> None:
        super().__init__(project_directory)
        self._builder = _MaturinBuilder(["pdm", "run"], self)
        warnings.warn(
            "Maturin + PDM project support is deprecated and will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )

    def disable_default_build(self) -> None:
        self._builder.disable_default_build()

    def enable_zig_build(self, targets: Collection[MaturinZigTarget]) -> None:
        """
        :param targets: Collection of MaturinTargets to cross-compile to using zig.
        """
        self._builder.enable_zig_build(targets)

    def add_build_environment_variable(self, key: str, value: str) -> None:
        self._builder.add_build_environment_variable(key, value)

    def get_managed_environment(self) -> ManagedEnvironment:
        return MaturinPdmManagedEnvironment(self.project_directory)

    def build(self, output_directory: Path) -> list[Path]:
        return self._builder.build(output_directory)


class MaturinPdmManagedEnvironment(PDMManagedEnvironment):
    def always_install(self) -> bool:
        return True


class MaturinUvPythonBuildSystem(UvPythonBuildSystem):
    """A maturin-backed version of the UV build system, that invokes the maturin build-backend.
    Can be enabled by adding the following to the local pyproject.yaml:
    ```toml
    [build-system]
    requires = ["maturin~=1.0"]
    build-backend = "maturin"
    ```
    """

    name = "Maturin UV"

    def __init__(self, project_directory: Path) -> None:
        super().__init__(project_directory)
        # We use the build requirement to do custom Maturin builds
        self._builder = _MaturinBuilder(
            ["uv", "tool", "run", *chain.from_iterable(("--with", r) for r in self._get_build_requirements())],
            self,
        )

    def disable_default_build(self) -> None:
        self._builder.disable_default_build()

    def enable_zig_build(self, targets: Collection[MaturinZigTarget]) -> None:
        """
        :param targets: Collection of MaturinTargets to cross-compile to using zig.
        """
        self._builder.enable_zig_build(targets)

    def add_build_environment_variable(self, key: str, value: str) -> None:
        self._builder.add_build_environment_variable(key, value)

    def build_v2(self, settings: PythonSettings, output_directory: Path) -> list[Path]:
        return self._builder.build(output_directory)

    def _get_build_requirements(self) -> Collection[str]:
        pyproject_toml = self.project_directory / "pyproject.toml"
        toml = TomlFile.read(pyproject_toml)
        return toml.get("build-system", {}).get("requires", [])  # type: ignore[no-any-return]
