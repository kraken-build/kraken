import logging
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from kraken.common import http
from kraken.core import Project
from kraken.std.helm import HelmPackageTask, HelmPushTask, helm_settings

from tests.kraken_std.util.docker import DockerServiceManager

logger = logging.getLogger(__name__)

USER_NAME = "user"
USER_PASS = "user"
REGISTRY_PORT = 5000


@pytest.fixture
def oci_registry(docker_service_manager: DockerServiceManager) -> Iterator[str]:  # noqa: F811
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a htpasswd file for the registry.
        logger.info("Generating htpasswd for OCI registry")
        htpasswd_content = docker_service_manager.run(
            "httpd:2",
            entrypoint="htpasswd",
            args=["-Bbn", USER_NAME, USER_PASS],
            capture_output=True,
        ).output
        htpasswd = Path(tempdir) / "htpasswd"
        htpasswd.write_bytes(htpasswd_content)

        # Start the registry.
        logger.info("Starting OCI registry")
        container = docker_service_manager.run(
            "registry",
            detach=True,
            ports=["5000"],
            volumes=[f"{htpasswd.absolute()}:/auth/htpasswd"],
            env={
                "REGISTRY_AUTH": "htpasswd",
                "REGISTRY_AUTH_HTPASSWD_REALM": "Registry Realm",
                "REGISTRY_AUTH_HTPASSWD_PATH": "/auth/htpasswd",
            },
        )

        time.sleep(0.5)
        port = container.ports["5000/tcp"][0]["HostPort"]
        yield f"localhost:{port}"


def test__helm_push_to_oci_registry(kraken_project: Project, oci_registry: str) -> None:
    """This integration test publishes a Helm chart to a local registry and checks if after publishing it, the
    chart can be accessed via the registry."""

    helm_settings(kraken_project).add_auth(oci_registry, USER_NAME, USER_PASS, insecure=True)
    package = kraken_project.task("helmPackage", HelmPackageTask)
    package.chart_directory = Path(__file__).parent / "data" / "example-chart"

    push = kraken_project.task("helmPush", HelmPushTask)
    push.chart_tarball = package.chart_tarball
    push.registry = f"oci://{oci_registry}/example"

    kraken_project.context.execute([":helmPush"])
    response = http.get(f"http://{oci_registry}/v2/example/example-chart/tags/list", auth=(USER_NAME, USER_PASS))
    response.raise_for_status()
    tags = response.json()
    assert tags == {"name": "example/example-chart", "tags": ["0.1.0"]}
