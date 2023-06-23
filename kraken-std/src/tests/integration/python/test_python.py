import filecmp
import logging
import os
import shutil
import tarfile
import unittest.mock
from pathlib import Path
from typing import Type, TypeVar

import pytest
import tomli
from kraken.common import not_none
from kraken.core import Context, Project

from kraken.std import python
from kraken.std.python.buildsystem.pdm import PdmPyprojectHandler
from kraken.std.python.buildsystem.poetry import PoetryPyprojectHandler
from kraken.std.python.pyproject import Pyproject
from tests.util.docker import DockerServiceManager

logger = logging.getLogger(__name__)
PYPISERVER_PORT = 23213
USER_NAME = "integration-test-user"
USER_PASS = "password-for-integration-test"


@pytest.fixture
def pypiserver(docker_service_manager: DockerServiceManager, tempdir: Path) -> str:
    # Create a htpasswd file for the registry.
    logger.info("Generating htpasswd for Pypiserver")
    htpasswd_content = not_none(
        docker_service_manager.run(
            "httpd:2",
            entrypoint="htpasswd",
            args=["-Bbn", USER_NAME, USER_PASS],
            capture_output=True,
        )
    )
    htpasswd = tempdir / "htpasswd"
    htpasswd.write_bytes(htpasswd_content)

    index_url = f"http://localhost:{PYPISERVER_PORT}/simple"
    docker_service_manager.run(
        "pypiserver/pypiserver:latest",
        ["--passwords", "/.htpasswd", "-a", "update"],
        ports=[f"{PYPISERVER_PORT}:8080"],
        volumes=[f"{htpasswd.absolute()}:/.htpasswd"],
        detach=True,
        probe=("GET", index_url),
    )
    logger.info("Started local Pypiserver at %s", index_url)
    return index_url


@pytest.mark.parametrize(
    "project_dir",
    [
        pytest.param(
            "poetry-project",
            marks=pytest.mark.xfail(
                reason="""
                    There appears to be an issue with Poetry 1.2.x and Pypiserver where the hashsums don't add up.
                    Example error message:

                        Retrieved digest for link poetry_project-0.1.0-py3-none-any.whl(md5:6340bed3198ccf181970f82cf6220f78)
                        not in poetry.lock metadata ['sha256:a2916a4e6ccb4c2f43f0ee9fb7fb1331962b9ec061f967c642fcfb9dbda435f3',
                        'sha256:80a47720d855408d426e835fc6088ed3aba2d0238611e16b483efe8e063d71ee']
                """  # noqa: E501
            ),
        ),
        "slap-project",
        "pdm-project",
    ],
)
@unittest.mock.patch.dict(os.environ, {})
def test__python_project_install_lint_and_publish(
    project_dir: str,
    kraken_ctx: Context,
    tempdir: Path,
    pypiserver: str,
) -> None:
    consumer_dir = project_dir + "-consumer"

    # Copy the projects to the temporary directory.
    shutil.copytree(Path(__file__).parent / "data" / project_dir, tempdir / project_dir)
    shutil.copytree(Path(__file__).parent / "data" / consumer_dir, tempdir / consumer_dir)

    # TODO (@NiklasRosenstein): Make sure Poetry installs the environment locally so it gets cleaned up
    #       with the temporary directory.

    logger.info("Loading and executing Kraken project (%s)", tempdir / project_dir)
    os.environ["LOCAL_PACKAGE_INDEX"] = pypiserver
    os.environ["LOCAL_USER"] = USER_NAME
    os.environ["LOCAL_PASSWORD"] = USER_PASS
    kraken_ctx.load_project(directory=tempdir / project_dir)
    kraken_ctx.execute([":lint", ":publish"])

    # Try to run the "consumer" project.
    logger.info("Loading and executing Kraken project (%s)", tempdir / consumer_dir)
    Context.__init__(kraken_ctx, kraken_ctx.build_directory)
    kraken_ctx.load_project(directory=tempdir / consumer_dir)
    kraken_ctx.execute([":python.install"])
    # TODO (@NiklasRosenstein): Test importing the consumer project.


@unittest.mock.patch.dict(os.environ, {})
def test__python_project_upgrade_python_version_string(
    kraken_ctx: Context,
    kraken_project: Project,
) -> None:
    tempdir = kraken_project.directory

    project_dir = "version-project"
    # tempdir /= project_dir
    build_as_version = "9.9.9a1"
    init_file = "src/version_project/__init__.py"
    original_dir = Path(__file__).parent / "data" / project_dir
    project_dist = kraken_project.build_directory / "python-dist"

    # Copy the projects to the temporary directory.
    shutil.copytree(original_dir, tempdir, dirs_exist_ok=True)
    logger.info("Loading and executing Kraken project (%s)", tempdir)

    pyproject = Pyproject.read(original_dir / "pyproject.toml")
    local_build_system = python.buildsystem.detect_build_system(tempdir)
    assert local_build_system is not None
    assert local_build_system.get_pyproject_reader(pyproject) is not None
    assert local_build_system.get_pyproject_reader(pyproject).get_name() == "version-project"
    python.settings.python_settings(project=kraken_project, build_system=local_build_system)
    python.build(as_version=build_as_version, project=kraken_project)
    kraken_ctx.execute([":build"])

    # Check if files that were supposed to be temporarily modified are the same after the build.
    assert filecmp.cmp(original_dir / "pyproject.toml", tempdir / "pyproject.toml", shallow=False)
    assert filecmp.cmp(original_dir / init_file, tempdir / init_file, shallow=False)
    # Check if generated files are named following proper version.
    assert Path(project_dist / f"version_project-{build_as_version}.tar.gz").is_file()
    assert Path(project_dist / f"version_project-{build_as_version}-py3-none-any.whl").is_file()
    with tarfile.open(project_dist / f"version_project-{build_as_version}.tar.gz", "r:gz") as tar:
        # Check if generated files store proper version.
        init_file_ext = tar.extractfile(f"version_project-{build_as_version}/{init_file}")
        assert init_file_ext is not None, ".tar.gz file does not contain an '__init__.py'"
        assert f'__version__ = "{build_as_version}"' in init_file_ext.read().decode("UTF-8")
        conf_file = tar.extractfile(f"version_project-{build_as_version}/pyproject.toml")
        assert conf_file is not None, ".tar.gz file does not contain an 'pyproject.toml'"
        assert build_as_version == tomli.loads(conf_file.read().decode("UTF-8"))["tool"]["poetry"]["version"]


M = TypeVar("M", PdmPyprojectHandler, PoetryPyprojectHandler)


@pytest.mark.parametrize(
    "project_dir, reader, expected_python_version",
    [
        ("poetry-project", PoetryPyprojectHandler, "^3.7"),
        ("slap-project", PoetryPyprojectHandler, "^3.6"),
        ("pdm-project", PdmPyprojectHandler, ">=3.9"),
    ],
)
@unittest.mock.patch.dict(os.environ, {})
def test__python_pyproject_reads_correct_data(
    project_dir: str,
    reader: Type[M],
    expected_python_version: str,
    kraken_project: Project,
) -> None:
    # Copy the projects to the temporary directory.
    new_dir = kraken_project.directory / project_dir
    shutil.copytree(Path(__file__).parent / "data" / project_dir, new_dir)

    pyproject = Pyproject.read(new_dir / "pyproject.toml")
    local_build_system = python.buildsystem.detect_build_system(new_dir)
    assert local_build_system is not None
    assert local_build_system.get_pyproject_reader(pyproject) is not None
    assert local_build_system.get_pyproject_reader(pyproject).get_name() == project_dir
    assert local_build_system.get_pyproject_reader(pyproject).get_version() == expected_python_version

    spec = reader(pyproject)

    assert spec.get_name() == project_dir
    assert spec.get_version() == expected_python_version
