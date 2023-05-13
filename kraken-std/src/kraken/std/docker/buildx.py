from __future__ import annotations

import os
import re
import subprocess as sp
from pathlib import Path

from kraken.common import flatten, not_none
from kraken.core.api import Project, TaskStatus

from kraken.std.docker.util import update_run_commands

from . import DockerBuildTask


class BuildxBuildTask(DockerBuildTask):
    """Implements building a Docker image with Buildx."""

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.preprocess_dockerfile.set(True)

    # DockerBuildTask

    def _preprocess_dockerfile(self, dockerfile: Path) -> str:
        mount_string = " ".join(f"--mount=type=secret,id={sec}" for sec in self.secrets.get().keys()) + " "
        return update_run_commands(dockerfile.read_text(), prefix=mount_string)

    # Task

    def finalize(self) -> None:
        if not self.load.get() and not self.push.get():
            self.logger.info("activating --load because one of --load or --push is necessary with Buildx")
            self.load.set(True)
        return super().finalize()

    def execute(self) -> TaskStatus:
        inspect_response = sp.check_output(["docker", "buildx", "inspect"]).decode()
        if re.search(r"Driver:\s*docker\n", inspect_response) and self.cache_repo.get():
            self.logger.info(
                "creating new Buildx driver, reason: current driver is Docker which does not support cache exports"
            )
            sp.check_call(["docker", "buildx", "create", "--use"])

        command = ["docker", "buildx", "build", str(self.build_context.get().absolute())]
        if self.dockerfile.is_filled():
            command += ["-f", str(self.dockerfile.get().absolute())]
        if self.platform.is_filled():
            command += ["--platform", str(self.platform.get())]
        command += flatten(["--build-arg", f"{k}={v}"] for k, v in self.build_args.get().items())
        command += flatten(["--secret", f"id={k}"] for k in self.secrets.get())
        if self.cache_repo.get():
            # NOTE (@NiklasRosenstein): Buildx does not allow leading underscores, while Kaniko and Artifactory do.
            command += ["--cache-to", f"type=registry,ref={not_none(self.cache_repo.get())}"]
            command += ["--cache-from", f"type=registry,ref={not_none(self.cache_repo.get())}"]
        if not self.cache.get():
            command += ["--no-cache"]
        command += flatten(["--tag", t] for t in self.tags.get())
        if self.push.get():
            command += ["--push"]
        if self.squash.get():
            command += ["--squash"]
        if self.target.get():
            command += ["--target", not_none(self.target.get())]
        if self.image_output_file.get():
            command += ["--output", f"type=tar,dest={self.image_output_file.get()}"]
        if self.load.get():
            command += ["--load"]

        # Buildx will take the secret from the environment variables.
        env = os.environ.copy()
        env.update(self.secrets.get())

        # TODO (@nrosenstein): docker login for auth

        self.logger.info("%s", command)
        result = sp.call(command, env=env, cwd=self.project.directory)
        return TaskStatus.from_exit_code(command, result)
