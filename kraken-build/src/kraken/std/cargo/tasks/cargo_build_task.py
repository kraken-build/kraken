from __future__ import annotations

import os
import shlex
import subprocess as sp
import time
from dataclasses import dataclass
from pathlib import Path

from kraken.core import Project, Property, Task, TaskStatus
from kraken.std.cargo.manifest import ArtifactKind, CargoMetadata
from kraken.std.descriptors.resource import BinaryArtifact, LibraryArtifact


@dataclass
class CargoBinaryArtifact(BinaryArtifact):
    pass


@dataclass
class CargoLibraryArtifact(LibraryArtifact):
    pass


class CargoBuildTask(Task):
    """This task runs `cargo build` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    #: The build target (debug or release). If this is anything else, the :attr:`out_binaries` will be set
    #: to an empty list instead of parsed from the Cargo manifest.
    target: Property[str]

    #: Additional arguments to pass to the Cargo command-line.
    additional_args: Property[list[str]] = Property.default_factory(list)

    #: Whether to build incrementally or not.
    incremental: Property[bool | None] = Property.default(None)

    #: Whether to pass --locked to cargo or not.
    #:
    #: When set to None, --locked is passed if Cargo.lock exists.
    locked: Property[bool | None] = Property.default(None)

    #: Environment variables for the Cargo command.
    env: Property[dict[str, str]] = Property.default_factory(dict)

    #: Number of times to retry before failing this job
    retry_attempts: Property[int] = Property.default(0)

    #: An output property for the Cargo binaries that are being produced by this build.
    out_binaries: Property[list[CargoBinaryArtifact]] = Property.output()

    #: An output property for the Cargo libraries that are being produced by this build.
    out_libraries: Property[list[CargoLibraryArtifact]] = Property.output()

    #: Flag indicating if we should execute this command from the project directory
    from_project_dir: Property[bool] = Property.default(False)

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)

    def get_description(self) -> str | None:
        command = self.get_cargo_command({})
        self.make_safe(command, {})
        return f"Run `{' '.join(command)}`."

    def get_cargo_command_additional_flags(self) -> list[str]:
        return shlex.split(os.environ.get("KRAKEN_CARGO_BUILD_FLAGS", ""))

    def should_add_locked_flag(self) -> bool:
        locked = self.locked.get()
        if locked is None:
            # pass --locked if we have a lock file
            # since we may be in a workspace member, we need to search up!
            for parent in (Path.cwd() / "Cargo.toml").parents:
                if (parent / "Cargo.lock").exists():
                    return True
        elif locked:
            # if locked is True, we should *always* pass --locked.
            # the expectation is that the command will fail w/o Cargo.lock.
            return True
        return False

    def get_additional_args(self) -> list[str]:
        args = self.additional_args.get()
        if "--locked" not in args and self.should_add_locked_flag():
            args = ["--locked", *args]
        return args

    def get_cargo_command(self, env: dict[str, str]) -> list[str]:
        incremental = self.incremental.get()
        if incremental is not None:
            env["CARGO_INCREMENTAL"] = "1" if incremental else "0"
        return ["cargo", "build"] + self.get_additional_args()

    def make_safe(self, args: list[str], env: dict[str, str]) -> None:
        pass

    def execute(self) -> TaskStatus:
        env = self.env.get()
        command = self.get_cargo_command(env) + self.get_cargo_command_additional_flags()

        safe_command = command[:]
        safe_env = env.copy()
        self.make_safe(safe_command, safe_env)
        self.logger.info("%s [env: %s]", safe_command, safe_env)

        out_binaries: list[CargoBinaryArtifact] = []
        out_libraries_candidates: list[CargoLibraryArtifact] = []
        if self.target.get_or(None) in ("debug", "release"):
            # Expose the output binaries that are produced by this task.
            # We only expect a binary to be built if the target is debug or release.
            manifest = CargoMetadata.read(self.project.directory, self.from_project_dir.get())
            target_dir = manifest.target_directory / self.target.get()
            for artifact in manifest.artifacts:
                # Rust binaries have an extensionless name whereas libraries are prefixed with "lib" and suffixed with
                #
                # - ".rlib" for Rust libraries
                # - ".so" (Linux), ".dylib" (macOS) or ".dll" (Windows) for dynamic Rust and system libraries
                # - ".a" (Linux, macOS) or ".lib" (Windows) for static system libraries
                if artifact.kind is ArtifactKind.BIN:
                    out_binaries.append(CargoBinaryArtifact(artifact.name, target_dir / artifact.name))
                elif artifact.kind is ArtifactKind.LIB:
                    base_name = f"lib{artifact.name}"
                    for file_extension in ["rlib", "so", "dylib", "dll", "a", "lib"]:
                        filename = ".".join([base_name.replace("-", "_"), file_extension])
                        out_libraries_candidates.append(CargoLibraryArtifact(base_name, target_dir / filename))

        total_attempts = self.retry_attempts.get() + 1

        result = -1
        while total_attempts > 0:
            result = sp.call(command, cwd=self.project.directory, env={**os.environ, **env})

            if result == 0:
                # Check that binaries which were due have been built.
                for out_bin in out_binaries:
                    assert out_bin.path.is_file(), out_bin
                self.out_binaries.set(out_binaries)

                # Check that at least one library has been built if libraries were due.
                out_libraries = []
                if len(out_libraries_candidates) != 0:
                    for out_libraries_candidate in out_libraries_candidates:
                        # Since we generate all possible file extensions, we must only keep the ones that exist
                        if out_libraries_candidate.path.is_file():
                            out_libraries.append(out_libraries_candidate)
                    assert (
                        len(out_libraries) != 0
                    ), f'No libraries were built even though some were due, e.g. "{out_libraries_candidates[0].name}"'
                self.out_libraries.set(out_libraries)
                break
            else:
                total_attempts -= 1
                self.logger.warn("%s failed with result %s", safe_command, result)
                self.logger.warn("There are %s attempts remaining", total_attempts)
                if total_attempts > 0:
                    self.logger.info("Waiting for 10 seconds before retrying..")
                    time.sleep(10)

        return TaskStatus.from_exit_code(safe_command, result)
