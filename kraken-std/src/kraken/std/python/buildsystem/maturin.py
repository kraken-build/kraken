""" Implements Maturin as a build system for kraken-std. """

from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Optional

from kraken.common.path import is_relative_to

from ...cargo.manifest import CargoMetadata
from ..pyproject import PoetryPyproject, Pyproject, SpecializedPyproject
from ..settings import PythonSettings
from . import ManagedEnvironment
from .poetry import PoetryManagedEnvironment, PoetryPythonBuildSystem

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
    rustflags: Optional[str] = None
    ld_library_path: Optional[str] = None
    macos_sdk_root: Optional[Path] = None
    manylinux: bool = True
    zig_features: Collection[str] = ()


class MaturinPythonBuildSystem(PoetryPythonBuildSystem):
    """A maturin-backed version of the Poetry build system, that invokes the maturin build-backend.
    Can be enabled by adding the following to the local pyproject.yaml:
    ```toml
    [tool.poetry.dev-dependencies]
    maturin = "0.13.7"

    [build-system]
    requires = ["maturin>=0.13,<0.14"]
    build-backend = "maturin"
    ```
    """

    name = "Maturin"

    def __init__(self, project_directory: Path) -> None:
        super().__init__(project_directory)
        self._default_build = True
        self._zig_targets: List[MaturinZigTarget] = []

    def get_pyproject_reader(self, pyproject: Pyproject) -> SpecializedPyproject:
        return PoetryPyproject(pyproject)

    def disable_default_build(self) -> None:
        self._default_build = False

    def enable_zig_build(
        self,
        targets: Collection[str | MaturinZigTarget] = (),
        features: Collection[str] = (),
        macos_sdk_root: Path | None = None,
    ) -> None:
        """
        :param targets: Collection of MaturinTargets to cross-compile to using zig.
        :param features: deprecated, do not use.
        :param macos_sdk_root: deprecated, do not use.
        """
        self._zig_targets.clear()
        for target in targets:
            if isinstance(target, str):
                self._zig_targets.append(
                    MaturinZigTarget(target=target, macos_sdk_root=macos_sdk_root, zig_features=features)
                )
            else:
                self._zig_targets.append(target)

    def get_managed_environment(self) -> ManagedEnvironment:
        return MaturinManagedEnvironment(self.project_directory)

    def update_pyproject(self, settings: PythonSettings, pyproject: Pyproject) -> None:
        super().update_pyproject(settings, pyproject)
        poetry_pyproj = PoetryPyproject(pyproject)
        poetry_pyproj.synchronize_project_section_to_poetry_state()

    def build(self, output_directory: Path, as_version: str | None = None) -> list[Path]:
        # We set the version
        old_poetry_version = None
        old_project_version = None
        pyproject_path = self.project_directory / "pyproject.toml"
        if as_version is not None:
            pyproject = Pyproject.read(pyproject_path)
            poetry_pyproj = PoetryPyproject(pyproject)
            old_poetry_version = poetry_pyproj.set_version(as_version)
            old_project_version = pyproject.set_core_metadata_version(as_version)
            pyproject.save()

        # We cleanup target dir
        metadata = CargoMetadata.read(self.project_directory)
        dist_dir = metadata.target_directory / "wheels"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        # We run the actual build
        if self._default_build:
            command = ["poetry", "run", "maturin", "build", "--release"]
            logger.info("%s", command)
            sp.check_call(command, cwd=self.project_directory)
        for target in self._zig_targets:
            command = [
                "poetry",
                "run",
                "maturin",
                "build",
                "--release",
                "--zig",
                "--target",
                target.target,
                "--features",
                ",".join(target.zig_features),
            ]
            if not target.manylinux:
                command.append("--manylinux")
                command.append("off")
            logger.info("%s", command)
            env = os.environ.copy()
            if target.target.endswith("-apple-darwin"):
                if target.macos_sdk_root is not None:
                    env["SDKROOT"] = str(target.macos_sdk_root.resolve())
                elif "SDKROOT" not in env:
                    logger.error(f"No macOS SDKROOT set for the target {target}")
            if target.rustflags is not None:
                env["RUSTFLAGS"] = target.rustflags
            if target.ld_library_path is not None:
                env["LD_LIBRARY_PATH"] = target.ld_library_path
            sp.check_call(command, cwd=self.project_directory, env=env)

        # We get the output files
        src_files = list(dist_dir.iterdir())
        dst_files = [output_directory / path.name for path in src_files]
        for src, dst in zip(src_files, dst_files):
            shutil.move(str(src), dst)

        # Unless the output directory is a subdirectory of the dist_dir, we remove the dist dir again.
        if not is_relative_to(output_directory, dist_dir):
            shutil.rmtree(dist_dir)

        if as_version is not None:
            # We roll back the version
            pyproject = Pyproject.read(pyproject_path)
            poetry_pyproj = PoetryPyproject(pyproject)
            poetry_pyproj.set_version(old_poetry_version)
            pyproject.set_core_metadata_version(old_project_version)
            pyproject.save()

        return dst_files


class MaturinManagedEnvironment(PoetryManagedEnvironment):
    def install(self, settings: PythonSettings) -> None:
        super().install(settings)
        command = ["poetry", "run", "maturin", "develop"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory)

    def always_install(self) -> bool:
        return True
