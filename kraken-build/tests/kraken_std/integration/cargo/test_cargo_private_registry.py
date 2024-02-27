"""This test is an end-to-end test to publish and consume crates from Artifactory/Cloudsmith. It performs the
following steps:

* Create a temporary Cargo repository in Artifactory/Cloudsmith
* Publish the `data/hello-world-lib` using the :func:`cargo_publish()` task
* Consume the just published library in `data/hello-world-app` using the :func:`cargo_build()` task

Without injecting the HTTP basic authentication credentials into the Cargo publish and build steps, we
expect the publish and/or build step to fail.

The test runs in a new temporary `CARGO_HOME` directory to ensure that Cargo has to freshly fetch the
Artifactory/Cloudsmith repository Git index every time.

!!! note

    This integration tests requires live remote repository credentials with enough permissions to create and delete
    repositories and to create a new user with access to the repository. If we get setting up an actual Artifactory
    or Cloudsmith instance within the tests, it would be very nice, but until then we need to inject these credentials
    in CI via an environment variable. Unless the environment variable is present, the test will be skipped.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import random
import shutil
import subprocess as sp
import time
import unittest.mock
from pathlib import Path

import pytest

from kraken.core import BuildError
from kraken.core.testing import kraken_ctx, kraken_project
from kraken.std.cargo import (
    cargo_auth_proxy,
    cargo_build,
    cargo_check_toolchain_version,
    cargo_publish,
    cargo_registry,
    cargo_sync_config,
)
from tests.kraken_std.util.docker import DockerServiceManager
from tests.resources import example_dir

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CargoRepositoryWithAuth:
    name: str
    index_url: str
    creds: tuple[str, str] | None
    token: str | None


def publish_lib_and_build_app(repository: CargoRepositoryWithAuth | None, tempdir: Path) -> None:
    # Copy the Cargo project files to a temporary directory.
    for item in ["cargo-hello-world-lib", "cargo-hello-world-app"]:
        shutil.copytree(example_dir(item), tempdir / item)

    app_dir = tempdir.joinpath("cargo-hello-world-app")
    lib_dir = tempdir.joinpath("cargo-hello-world-lib")

    cargo_registry_id = "private-repo"
    publish_version = ".".join(str(random.randint(0, 999)) for _ in range(3))
    logger.info("==== Publish version is %s", publish_version)

    with unittest.mock.patch.dict(os.environ, {"CARGO_HOME": str(tempdir)}):
        # Build the library and publish it to Artifactory.
        if repository:
            logger.info(
                "Publishing cargo-hello-world-lib to Cargo repository %r (%r)",
                repository.name,
                repository.index_url,
            )
        else:
            logger.info("Building data/hello-world-lib")

        with kraken_ctx() as ctx, kraken_project(ctx) as project1:
            project1.directory = lib_dir
            if repository:
                cargo_registry(
                    cargo_registry_id,
                    repository.index_url,
                    read_credentials=repository.creds,
                    publish_token=repository.token,
                )
            cargo_auth_proxy()
            task = cargo_sync_config()
            task.git_fetch_with_cli.set(True)
            cargo_check_toolchain_version(minimal_version="1.60")
            cargo_publish(
                cargo_registry_id, version=publish_version, cargo_toml_file=project1.directory.joinpath("Cargo.toml")
            )
            if repository:
                project1.context.execute(["fmt", "lint", "publish"])
            else:
                project1.context.execute(["fmt", "lint", "build"])

        if not repository:
            return

        num_tries = 3
        for idx in range(num_tries):
            try:
                # Compile the application, expecting that it can consume from the freshly published library.
                logger.info(
                    "Building data/hello-world-app which consumes hello-world-lib from Cargo repository %r (%r)",
                    repository.name,
                    repository.index_url,
                )
                with kraken_ctx() as ctx, kraken_project(ctx) as project2:
                    project2.directory = app_dir
                    cargo_toml = project2.directory / "Cargo.toml"
                    cargo_toml.write_text(cargo_toml.read_text().replace("$VERSION", publish_version))
                    cargo_registry(
                        cargo_registry_id,
                        repository.index_url,
                        read_credentials=repository.creds,
                    )
                    cargo_auth_proxy()
                    sync_task = cargo_sync_config()
                    sync_task.git_fetch_with_cli.set(True)
                    build_task = cargo_build("debug")
                    build_task.from_project_dir = True
                    project2.context.execute(["fmt", "build"])

                # Running the application should give "Hello from hello-world-lib!".
                output = sp.check_output([app_dir / "target" / "debug" / "hello-world-app"]).decode()
                assert output.strip() == "Hello from hello-world-lib!"
            except BuildError as exc:
                logger.error(
                    "Encountered a build error (%s); most likely that is because the Cargo repository "
                    "requires some time to index the package.",
                    exc,
                )
                if idx == (num_tries - 1):
                    raise
                logger.info("Giving repository time to index (10s) ...")
                time.sleep(10)


@pytest.fixture()
def private_registry(docker_service_manager: DockerServiceManager) -> str:
    port = "35504"
    host = "0.0.0.0"
    address = f"{host}:{port}"
    index_url = f"http://{address}/git"
    docker_service_manager.run(
        "ghcr.io/d-e-s-o/cargo-http-registry:latest",
        [
            "/tmp/test-registry",
            "--addr",
            address,
        ],
        ports=[f"{port}:{port}"],
        detach=True,
    )
    logger.info("Started local cargo registry at %s", index_url)
    return index_url


def test__private_cargo_registry_publish_and_consume(tempdir: Path, private_registry: str) -> None:
    repository = CargoRepositoryWithAuth(
        "kraken-std-cargo-integration-test", private_registry, None, "xxxxxxxxxxxxxxxxxxxxxx"
    )
    publish_lib_and_build_app(repository, tempdir)


def test_cargo_build(tempdir: Path) -> None:
    publish_lib_and_build_app(None, tempdir)
