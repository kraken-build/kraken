from __future__ import annotations

import contextlib
import shlex
import tempfile
from collections.abc import Sequence
from pathlib import Path

from kraken.common import flatten
from kraken.core import Project, Property
from kraken.std.docker.util.dockerapi import docker_load, docker_run
from kraken.std.docker.util.dockerfile import render_docker_auth, update_run_commands

from .base_build_task import BaseBuildTask


class KanikoBuildTask(BaseBuildTask):
    """
    An implementation for building Docker images with Kaniko.

    In order to make secrets available in the Dockerfile under `/run/secrets`, and `RUN` command that is executed
    by the root user will be surrounded by additional shell commands to link `/kaniko/secrets` to `/run/secrets`.
    This is to ensure a degree of compatibility with BuildKit, which mounts secrets to `/run/secrets` when using
    the `--secret` flag.

    However, this compatibility is limited because we can only actually create a at `/run/secrets` if the `RUN`
    command runs as root. Any command that is executed as a non-root user will not be able to access the secrets.
    We use a heuristic to detect this, but it is not perfect. If you need to use secrets in a `RUN` command that
    is executed as a non-root user, you will need to read from `/kaniko/secrets` instead.

    If you start from a base image that doesn't start as the root user, you will need to explicitly add a `USER`
    command to your Dockerfile to either inform the `KanikoBuildTask` that the subsequent commands are not run as
    root, or use it to switch to the root user. Otherwise, the `KanikoBuildTask` will assume that the subsequent
    commands are run as root and it can not know in advance if they are or not.
    """

    kaniko_image: Property[str] = Property.default("gcr.io/kaniko-project/executor:v1.9.0-debug")
    kaniko_context: Property[str] = Property.default("/workspace")
    kaniko_cache_copy_layers: Property[bool] = Property.default(True)
    kaniko_snapshot_mode: Property[str] = Property.default("redo")
    kaniko_secrets_mount_dir: Property[str] = Property.default("/kaniko/secrets")
    kaniko_secrets_from_env: Property[Sequence[str]] = Property.default(())
    kaniko_use_compressed_caching: Property[bool] = Property.default(True)

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.preprocess_dockerfile.set(True)

    def render_main_script(self, executor_command: list[str]) -> str:
        """Renders the shell script that will be executed in the Kaniko container."""

        docker_config = render_docker_auth(self.auth.get())

        script = []
        script += [
            "mkdir -p /kaniko/.docker",
            "cat << EOF > /kaniko/.docker/config.json",
            docker_config,
            "EOF",
        ]

        secrets_mount_dir = self.kaniko_secrets_mount_dir.get()
        if self.secrets.get():
            script += [f"mkdir -p {shlex.quote(secrets_mount_dir)}"]
            for secret, value in self.secrets.get().items():
                script += [f"echo {shlex.quote(value)} > {shlex.quote(secrets_mount_dir + '/' + secret)}"]
        if self.kaniko_secrets_from_env.get():
            for env in self.kaniko_secrets_from_env.get():
                script += [f"echo ${env} > {shlex.quote(secrets_mount_dir + '/' + env)}"]

        script += [" ".join(map(shlex.quote, executor_command))]
        return "\n".join(script)

    def get_kaniko_executor_command(self, dockerfile: str | None, tar_path: str | None) -> list[str]:
        if tar_path and not self.tags:
            raise ValueError("Need at least one destination (tag) when exporting to an image tarball")
        executor_command = ["/kaniko/executor"]
        executor_command += flatten(("--build-arg", f"{key}={value}") for key, value in self.build_args.get().items())
        cache_repo = self.cache_repo.get()
        if cache_repo:
            executor_command += ["--cache-repo", cache_repo]
        if self.cache.get_or(False):
            executor_command += ["--cache=true"]
        executor_command += flatten(("--destination", destination) for destination in self.tags.get())
        if dockerfile:
            executor_command += ["--dockerfile", dockerfile]
        if not self.push.get():
            executor_command += ["--no-push"]
        executor_command += ["--snapshotMode", self.kaniko_snapshot_mode.get()]
        if self.squash.get():
            executor_command += ["--single-snapshot"]
        if self.kaniko_cache_copy_layers.get():
            executor_command += ["--cache-copy-layers"]
        if not self.kaniko_use_compressed_caching.get():
            executor_command += ["--compressed-caching=false"]
        target = self.target.get()
        if target:
            executor_command += ["--target", target]
        if tar_path:
            executor_command += ["--tarPath", tar_path]
        executor_command += ["--context", self.kaniko_context.get()]
        return executor_command

    def _build(
        self,
        exit_stack: contextlib.ExitStack,
    ) -> None:
        volumes = [f"{self.build_context.get().absolute()}:{self.kaniko_context.get()}"]

        # If the Dockerfile is not relative to the build context, we need to mount it explicitly.
        dockerfile = self.dockerfile.get()
        in_container_dockerfile: str | None = None
        try:
            in_container_dockerfile = str(dockerfile.absolute().relative_to(self.build_context.get().absolute()))
        except ValueError:
            in_container_dockerfile = "/kaniko/Dockerfile"
            volumes += [f"{dockerfile.absolute()}:{in_container_dockerfile}"]

        # If the image needs to be loaded into the Docker daemon after building, we need to always
        # export it to a file.
        image_output_file = self.image_output_file.get_or(None)
        if self.load.get() and not image_output_file:
            tempdir = exit_stack.enter_context(tempfile.TemporaryDirectory())
            image_output_file = Path(tempdir) / "image.tgz"

        # Construct the tar path for inside the container.
        tar_path: str | None = None
        if image_output_file:
            volumes += [f"{image_output_file.parent.absolute()}:/kaniko/out"]
            tar_path = f"/kaniko/out/{image_output_file.name}"

        executor_command = self.get_kaniko_executor_command(in_container_dockerfile, tar_path)

        script = self.render_main_script(executor_command)

        result = docker_run(
            image=self.kaniko_image.get(),
            args=["sh", "-c", script],
            entrypoint="",
            remove=True,
            volumes=volumes,
            workdir=self.kaniko_context.get(),
            platform=self.platform.get_or(None),
        )

        if result != 0:
            raise Exception(f"Kaniko build failed with exit code {result}")

        if self.load.get():
            assert image_output_file is not None, "image_output_file is expected to be set when config.load == True"
            result = docker_load(image_output_file)
            if result != 0:
                raise Exception(f"Docker load failed with exit code {result}")

    # BaseBuildTask overrides

    def _preprocess_dockerfile(self, dockerfile: Path) -> str:
        return update_run_commands(
            dockerfile.read_text(),
            prefix="ln -sf /kaniko/secrets /run/secrets && ( ",
            suffix=" ); __ret=$?; unlink /run/secrets; exit $__ret",
            # We can only link to /run/secrets if the user running the command is the root user. In any other
            # case, we cannot link to /run/secrets and reading the secrets from /run/secrets in the Dockerfile
            # will fail.
            only_for_root_user=True,
        )

    # Task overrides

    def finalize(self) -> None:
        if self.cache.get() and not self.push.get() and not self.cache_repo.get():
            self.logger.warning(
                "Disabling cache in Kaniko build %s because it must be combined with push or cache_repo",
                self,
            )
            self.cache.set(False)
        cache_repo = self.cache_repo.get_or(None)
        if cache_repo and ":" in cache_repo:
            raise ValueError(f"Kaniko --cache-repo argument cannot contain `:` (got: {cache_repo!r})")
        return super().finalize()

    def execute(self) -> None:
        with contextlib.ExitStack() as exit_stack:
            self._build(exit_stack)
