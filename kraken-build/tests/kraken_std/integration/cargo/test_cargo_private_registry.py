"""This test is an end-to-end test to publish and consume crates from a private Cargo registry."""

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
from requests_mock import Mocker

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


def skip_publish_lib(repository: CargoRepositoryWithAuth, tempdir: Path) -> None:
    lib_dir = tempdir.joinpath("cargo-hello-world-lib")
    shutil.copytree(example_dir("cargo-hello-world-lib"), lib_dir)
    cargo_registry_id = "private-repo"

    with unittest.mock.patch.dict(os.environ, {"CARGO_HOME": str(tempdir)}):
        # Build the library and publish it to the registry.
        logger.info(
            "Publishing cargo-hello-world-lib to Cargo repository %r (%r)",
            repository.name,
            repository.index_url,
        )

        with kraken_ctx() as ctx, kraken_project(ctx) as project1:
            project1.directory = lib_dir
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
            publish_task = cargo_publish(
                cargo_registry_id,
                version="0.1.0",
                cargo_toml_file=project1.directory.joinpath("Cargo.toml"),
            )
            graph = project1.context.execute(["publish"])
            status = graph.get_status(publish_task)
            assert status is not None and status.is_skipped()


def publish_lib_and_build_app(repository: CargoRepositoryWithAuth, tempdir: Path) -> None:
    # Copy the Cargo project files to a temporary directory.
    for item in ["cargo-hello-world-lib", "cargo-hello-world-app"]:
        shutil.copytree(example_dir(item), tempdir / item)

    app_dir = tempdir.joinpath("cargo-hello-world-app")
    lib_dir = tempdir.joinpath("cargo-hello-world-lib")

    cargo_registry_id = "private-repo"
    publish_version = ".".join(str(random.randint(0, 999)) for _ in range(3))
    logger.info("==== Publish version is %s", publish_version)

    with unittest.mock.patch.dict(os.environ, {"CARGO_HOME": str(tempdir)}):
        # Build the library and publish it to the registry.
        logger.info(
            "Publishing cargo-hello-world-lib to Cargo repository %r (%r)",
            repository.name,
            repository.index_url,
        )

        with kraken_ctx() as ctx, kraken_project(ctx) as project1:
            project1.directory = lib_dir
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
                cargo_registry_id,
                version=publish_version,
                cargo_toml_file=project1.directory.joinpath("Cargo.toml"),
            )
            project1.context.execute(["fmt", "lint", "publish"])

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
                break
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


# NOTE(@niklas): It would be better if we could just create a new Cargo registry for each test instead of scoping
#       it to the session, however somehow `cargo publish` chooses the server's internal port for the
#       `/api/v1/crates/new` request even if we configure the host port instead.
#
#       Logs from mitmweb on `cargo publish --registry private-repo --token xxxxx`
#
#           - GET http://localhost:49321/git/info/refs?service=git-upload-pack HTTP/1.1
#           - GET http://localhost:49321/git/HEAD HTTP/1.1
#           - PUT http://0.0.0.0:35504/api/v1/crates/new HTTP/1.1
#
#       I suppose it's caused by the repository config served via the Git repository that directs Cargo to a separate
#       API endpoint. Until we can find a way to change this behavior, we need the container port and the host port
#       to be the same, which prevents us from running multiple test-scoped fixtures in parallel.
@pytest.fixture(scope="session")
def private_registry(docker_service_manager: DockerServiceManager) -> str:
    container = docker_service_manager.run(
        "ghcr.io/d-e-s-o/cargo-http-registry:latest",
        [
            "/tmp/test-registry",
            "--addr",
            "0.0.0.0:35504",
        ],
        ports=["35504:35504"],
        detach=True,
    )

    host = "localhost"
    port = container.ports["35504/tcp"][0]["HostPort"]
    index_url = f"http://{host}:{port}/git"
    logger.info("Started local cargo registry at %s", index_url)
    time.sleep(5)
    return index_url


def test__private_cargo_registry_publish_and_consume(tempdir: Path, private_registry: str) -> None:
    repository = CargoRepositoryWithAuth(
        "kraken-std-cargo-integration-test", private_registry, None, "xxxxxxxxxxxxxxxxxxxxxx"
    )
    publish_lib_and_build_app(repository, tempdir)


def test__mock_cargo_registry_skips_publish_if_exists(tempdir: Path, requests_mock: Mocker) -> None:
    registry_url = "http://0.0.0.0:35510"
    index_url = f"sparse+{registry_url}/"

    requests_mock.get(f"{registry_url}/config.json", text="{}")
    requests_mock.get(f"{registry_url}/he/ll/hello-world-lib", text='{"vers": "0.1.0"}')

    repository = CargoRepositoryWithAuth("kraken-std-cargo-integration-test", index_url, None, "xxxxxxxxxxxxxxxxxxxxxx")
    skip_publish_lib(repository, tempdir)
