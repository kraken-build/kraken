from __future__ import annotations

import os
import subprocess as sp
import tempfile
from pathlib import Path

from kraken.common import flatten, not_none
from kraken.core import Project, Property, TaskStatus
from kraken.std.docker.util.dockerfile import update_run_commands

from .base_build_task import BaseBuildTask


class DockerBuildTask(BaseBuildTask):
    """Implements building a Docker image using the native `docker build` command."""

    #: Whether to use Docker Buildkit. Enabled by default.
    native_use_buildkit: Property[bool] = Property.default(True)

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.preprocess_dockerfile.set(True)

    # BaseBuildTask overrides

    def _preprocess_dockerfile(self, dockerfile: Path) -> str:
        mount_string = " ".join(f"--mount=type=secret,id={sec}" for sec in self.secrets.get().keys()) + " "
        return update_run_commands(dockerfile.read_text(), prefix=mount_string)

    # Task overrides

    def finalize(self) -> None:
        if self.cache_repo.get() is not None:
            self.logger.warning("cache_repo is not supported for DockerBuildTask")
        if self.squash.get() is not None:
            self.logger.warning("squash is not supported for DockerBuildTask")
        if not self.load.get():
            self.logger.warning("load is not supported for DockerBuildTask, resulting image will always be loaded")
        if self.push.get() and not self.tags.get():
            raise ValueError(f"{self}.tags cannot be empty if .push is enabled")
        return super().finalize()

    def execute(self) -> TaskStatus:
        command = ["docker", "build", str(self.build_context.get().absolute())]
        if self.dockerfile.is_filled():
            command += ["-f", str(self.dockerfile.get().absolute())]
        if self.platform.is_filled():
            command += ["--platform", str(self.platform.get())]
        command += flatten(["--build-arg", f"{k}={v}"] for k, v in self.build_args.get().items())
        if self.cache_repo.get():
            # NOTE (@NiklasRosenstein): Buildx does not allow leading underscores, while Kaniko and Artifactory do.
            command += ["--cache-from", f"type=registry,ref={not_none(self.cache_repo.get())}"]
        if not self.cache.get():
            command += ["--no-cache"]
        command += flatten(["--tag", t] for t in self.tags.get())
        if self.target.get():
            command += ["--target", not_none(self.target.get())]
        if self.image_output_file.get():
            command += ["--output", f"type=tar,dest={self.image_output_file.get()}"]

        command += ["--pull", "--progress", "plain"]

        # Buildx will take the secret from the environment variasbles.
        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "1" if self.native_use_buildkit.get() else "0"

        # TODO (@nrosenstein): docker login for auth

        with tempfile.TemporaryDirectory() as tempdir:
            for key, value in self.secrets.get().items():
                secret_file = Path(tempdir) / key
                secret_file.write_text(value)
                command += ["--secret", f"id={key},src={secret_file}"]

            self.logger.info("%s", command)
            result = sp.call(command, env=env, cwd=self.project.directory)
            if result != 0:
                return TaskStatus.from_exit_code(command, result)

        if self.push.get():
            command = ["docker", "push"] + self.tags.get()
            self.logger.info("%s", command)
            result = sp.call(command, env=env, cwd=self.project.directory)

        return TaskStatus.succeeded()
