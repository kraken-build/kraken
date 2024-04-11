from __future__ import annotations

import os
import re
import subprocess as sp
from pathlib import Path

from kraken.common import flatten, not_none
from kraken.core import Project, Property, TaskStatus
from kraken.std.docker.util.dockerfile import update_run_commands

from .base_build_task import BaseBuildTask


class BuildxBuildTask(BaseBuildTask):
    """Implements building a Docker image with Buildx."""

    #: Whether to add provenance to the image manifest. Using this option, even when building for a single
    #: platform, a `list.manifest.json` is pushed instead of a `manifest.json`, which is why we default to
    #: `False`.
    provenance: Property[bool] = Property.default(False)

    cache_from: Property[str | None] = Property.default(None)
    cache_to: Property[str | None] = Property.default(None)

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.preprocess_dockerfile.set(True)

    # BaseBuildTask overrides

    def _preprocess_dockerfile(self, dockerfile: Path) -> str:
        mount_string = " ".join(f"--mount=type=secret,id={sec}" for sec in self.secrets.get().keys()) + " "
        return update_run_commands(dockerfile.read_text(), prefix=mount_string)

    # Task overrides

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
            command += ["--cache-from", f"type=registry,ref={not_none(self.cache_repo.get())}"]
            command += ["--cache-to", f"type=registry,ref={not_none(self.cache_repo.get())},mode=max,ignore-error=true"]
        if not self.cache.get():
            command += ["--no-cache"]
        if cache_from := self.cache_from.get():
            command += ["--cache-from", cache_from]
        if cache_to := self.cache_to.get():
            command += ["--cache-to", cache_to]
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
        command += [f"--provenance={'true' if self.provenance.get() else 'false'}"]

        # Buildx will take the secret from the environment variables.
        env = os.environ.copy()
        env.update(self.secrets.get())

        # TODO (@nrosenstein): docker login for auth

        self.logger.info("%s", command)
        result = sp.call(command, env=env, cwd=self.project.directory)
        return TaskStatus.from_exit_code(command, result)
