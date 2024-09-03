from __future__ import annotations

import contextlib
import subprocess as sp
import tempfile
import textwrap
from pathlib import Path

import pytest

from kraken.core import Project
from kraken.std.docker import BUILD_BACKENDS, build_docker_image
from kraken.std.util.render_file_task import RenderFileTask


@pytest.mark.parametrize("backend", BUILD_BACKENDS.keys())
def test__secrets_can_be_accessed_at_build_time_and_are_not_present_in_the_final_image(
    kraken_project: Project,
    backend: str,
) -> None:
    """Tests that secret file mounts work as expected, i.e. they can be read from `/run/secrets` and they
    do not make it into the final image."""

    secret_name = "MY_SECRET"
    secret_path = f"/run/secrets/{secret_name}"

    dockerfile_content = textwrap.dedent(
        f"""
        FROM alpine:latest as base
        RUN cat {secret_path}

        # Need to test that the secret is still available in the second build stage because of
        #    https://github.com/kraken-build/kraken-std/issues/10
        FROM base
        RUN cat {secret_path}
        """
    )

    if backend == "kaniko":
        dockerfile_content += "\nRUN ls /kaniko/secrets\nRUN ls /run/secrets"

    image_tag = f"kraken-integration-tests/test-secrets-{backend}:latest"

    with tempfile.TemporaryDirectory() as tempdir, contextlib.ExitStack() as exit_stack:
        kraken_project.directory = Path(tempdir)

        dockerfile = kraken_project.task("writeDockerfile", RenderFileTask)
        dockerfile.file = kraken_project.build_directory / "Dockerfile"
        dockerfile.content = dockerfile_content

        build_docker_image(
            name="buildDocker",
            dockerfile=dockerfile.file,
            secrets={secret_name: "Hello, World!"},
            cache=False,
            tags=[image_tag],
            load=True,
            backend=backend,
        )

        kraken_project.context.execute([":buildDocker"])

        exit_stack.callback(lambda: sp.check_call(["docker", "rmi", image_tag]))

        # Check that the secret files does not exist.
        command = ["sh", "-c", f"find {secret_path} 2>/dev/null || true"]
        output = sp.check_output(["docker", "run", "--rm", image_tag] + command).decode().strip()
        assert output == ""

        if backend == "kaniko":
            # Check that the secrets folder does not exist.
            # NOTE (@niklas.rosenstein): Buildx leaves the /run/secrets folder dangling
            command = ["sh", "-c", "find /run/secrets 2>/dev/null || true"]
            output = sp.check_output(["docker", "run", "--rm", image_tag] + command).decode().strip()
            assert output == ""

            # Check that the kaniko secrets dir does not exist.
            command = ["sh", "-c", "find /kaniko/secrets 2>/dev/null || true"]
            output = sp.check_output(["docker", "run", "--rm", image_tag] + command).decode().strip()
            assert output == ""
