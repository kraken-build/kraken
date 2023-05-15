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
import json
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
    cargo_bump_version,
    cargo_check_toolchain_version,
    cargo_publish,
    cargo_registry,
    cargo_sync_config,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CargoRepositoryWithAuth:
    name: str
    index_url: str
    user: str
    password: str
    token: str


def publish_lib_and_build_app(repository: CargoRepositoryWithAuth | None, tempdir: Path) -> None:
    # Copy the Cargo project files to a temporary directory.
    data_dir = tempdir
    data_source_dir = Path(__file__).parent / "data"
    for item in data_source_dir.iterdir():
        shutil.copytree(item, data_dir / item.name)

    cargo_registry_id = "private-repo"
    publish_version = ".".join(str(random.randint(0, 999)) for _ in range(3))
    logger.info("==== Publish version is %s", publish_version)

    with unittest.mock.patch.dict(os.environ, {"CARGO_HOME": str(tempdir)}):
        # Build the library and publish it to Artifactory.
        if repository:
            logger.info(
                "Publishing data/hello-world-lib to Cargo repository %r (%r)",
                repository.name,
                repository.index_url,
            )
        else:
            logger.info("Building data/hello-world-lib")

        with kraken_ctx() as ctx, kraken_project(ctx) as project1:
            project1.directory = data_dir / "hello-world-lib"
            if repository:
                cargo_registry(
                    cargo_registry_id,
                    repository.index_url,
                    read_credentials=(repository.user, repository.password),
                    publish_token=repository.token,
                )
            cargo_auth_proxy()
            task = cargo_sync_config()
            task.git_fetch_with_cli.set(True)
            cargo_check_toolchain_version(minimal_version="1.60")
            cargo_bump_version(version=publish_version)
            cargo_publish(cargo_registry_id)
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
                    project2.directory = data_dir / "hello-world-app"
                    cargo_toml = project2.directory / "Cargo.toml"
                    cargo_toml.write_text(cargo_toml.read_text().replace("$VERSION", publish_version))
                    cargo_registry(
                        cargo_registry_id,
                        repository.index_url,
                        read_credentials=(repository.user, repository.password),
                    )
                    cargo_auth_proxy()
                    cargo_sync_config()
                    cargo_build("debug")
                    project2.context.execute(["fmt", "build"])

                # Running the application should give "Hello from hello-world-lib!".
                output = sp.check_output(
                    [data_dir / "hello-world-app" / "target" / "debug" / "hello-world-app"]
                ).decode()
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


ARTIFACTORY_VAR = "ARTIFACTORY_INTEGRATION_TEST_CREDENTIALS"
CLOUDSMITH_VAR = "CLOUDSMITH_INTEGRATION_TEST_CREDENTIALS"


@pytest.mark.skipif(ARTIFACTORY_VAR not in os.environ, reason=f"{ARTIFACTORY_VAR} is not set")
@pytest.mark.xfail(reason="currently failing, see test artifactory is no longer active, see #32")
def test__artifactory_cargo_publish_and_consume(tempdir: Path) -> None:
    credentials = json.loads(os.environ[ARTIFACTORY_VAR])
    repository = CargoRepositoryWithAuth(
        "kraken-std-cargo-integration-test",
        credentials["url"] + f"/git/{os.environ['ARTIFACTORY_CARGO_REPOSITORY']}.git",
        credentials["user"],
        credentials["token"],
        "Bearer " + credentials["token"],
    )
    publish_lib_and_build_app(repository, tempdir)


@pytest.mark.skipif(CLOUDSMITH_VAR not in os.environ, reason=f"{CLOUDSMITH_VAR} is not set")
@pytest.mark.xfail(reason="currently failing, see #14")
def test__cloudsmith_cargo_publish_and_consume(tempdir: Path) -> None:
    credentials = json.loads(os.environ[CLOUDSMITH_VAR])
    repository = CargoRepositoryWithAuth(
        "kraken-std-cargo-integration-test",
        (
            f"https://dl.cloudsmith.io/basic/{credentials['owner']}/"
            f"{os.environ['CLOUDSMITH_CARGO_REPOSITORY']}/cargo/index.git"
        ),
        credentials["user"],
        credentials["api_key"],
        credentials["api_key"],
    )
    publish_lib_and_build_app(repository, tempdir)


def test_cargo_build(tempdir: Path) -> None:
    publish_lib_and_build_app(None, tempdir)
