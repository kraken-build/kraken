import filecmp
import logging
import os
import shutil
import tarfile
import tempfile
import unittest.mock
from collections.abc import Iterator
from pathlib import Path
from typing import TypeVar
from unittest.mock import patch

import httpx
import pytest
import tomli

from kraken.common.toml import TomlFile
from kraken.core import Context, Project
from kraken.std import python
from kraken.std.python.buildsystem.maturin import MaturinPoetryPyprojectHandler
from kraken.std.python.buildsystem.pdm import PdmPyprojectHandler
from kraken.std.python.buildsystem.poetry import PoetryPyprojectHandler
from kraken.std.python.buildsystem.uv import UvPyprojectHandler
from kraken.std.util.http import http_probe

from tests.kraken_std.util.docker import DockerServiceManager
from tests.resources import example_dir

logger = logging.getLogger(__name__)
USER_NAME = "integration-test-user"
USER_PASS = "password-for-integration-test"


@pytest.fixture(scope="session", autouse=True)
def deactivate_venv() -> Iterator[None]:
    with patch.dict(os.environ), tempfile.TemporaryDirectory() as tempdir:
        pdm_config = Path(tempdir + "/.pdm.toml")
        pdm_config.write_text(f'cache_dir = "{tempdir}/.pdm_cache"')
        os.environ.pop("VIRTUAL_ENV", None)
        os.environ.pop("VIRTUAL_ENV_PROMPT", None)
        os.environ["POETRY_VIRTUALENVS_IN_PROJECT"] = "true"
        os.environ["POETRY_CACHE_DIR"] = tempdir
        os.environ["PDM_CONFIG_FILE"] = str(pdm_config)
        yield


@pytest.fixture(scope="session")
def pypiserver(docker_service_manager: DockerServiceManager) -> str:
    with tempfile.TemporaryDirectory() as _tempdir:
        tempdir = Path(_tempdir)

        # Create a htpasswd file for the registry.
        logger.info("Generating htpasswd for Pypiserver")
        htpasswd_content = docker_service_manager.run(
            "httpd:2",
            entrypoint="htpasswd",
            args=["-Bbn", USER_NAME, USER_PASS],
            capture_output=True,
        ).output
        htpasswd = tempdir / "htpasswd"
        htpasswd.write_bytes(htpasswd_content)

        container = docker_service_manager.run(
            "pypiserver/pypiserver:latest",
            ["--passwords", "/.htpasswd", "-a", "update", "--hash-algo", "sha256"],
            ports=["8080"],
            volumes=[f"{htpasswd.absolute()}:/.htpasswd"],
            detach=True,
        )

        # host = container.ports["8080/tcp"][0]["HostIp"]
        host = "localhost"  # The container ports HostIp is 0.0.0.0, which PDM won't trust without extra config.
        port = container.ports["8080/tcp"][0]["HostPort"]
        index_url = f"http://{host}:{port}/simple"

        http_probe("GET", index_url)

        logger.info("Started local Pypiserver at %s", index_url)
        return index_url


@pytest.mark.parametrize(
    "project_dir",
    [
        "poetry-project",
        "slap-project",
        "pdm-project",
        "uv-project",
        "rust-poetry-project",
        "rust-pdm-project",
        # "rust-uv-project",  # See https://github.com/kraken-build/kraken/issues/356
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
    shutil.copytree(example_dir(project_dir), tempdir / project_dir)
    shutil.copytree(example_dir(consumer_dir), tempdir / consumer_dir)

    # Remove the .venv if it exists in the project directory to ensure a clean environment.
    venv_path = tempdir / project_dir / ".venv"
    if venv_path.exists():
        shutil.rmtree(venv_path)
    venv_path = tempdir / consumer_dir / ".venv"
    if venv_path.exists():
        shutil.rmtree(venv_path)

    logger.info("Loading and executing Kraken project (%s)", tempdir / project_dir)
    # TODO: mock the `os.environ` dict instead of mutating the global one
    os.environ["LOCAL_PACKAGE_INDEX"] = pypiserver
    os.environ["LOCAL_USER"] = USER_NAME
    os.environ["LOCAL_PASSWORD"] = USER_PASS
    # Make sure Poetry installs the environment locally so it gets cleaned up
    os.environ["POETRY_VIRTUALENVS_IN_PROJECT"] = "1"

    kraken_ctx.load_project(directory=tempdir / project_dir)
    kraken_ctx.execute([":lint", ":publish"])

    # Try to run the "consumer" project.
    logger.info("Loading and executing Kraken project (%s)", tempdir / consumer_dir)
    Context.__init__(kraken_ctx, kraken_ctx.build_directory)
    kraken_ctx.load_project(directory=tempdir / consumer_dir)

    # NOTE: The Slap project doesn't need an apply because we don't write the package index into the pyproject.toml.
    kraken_ctx.execute([":apply"])

    # For debugging
    package_state = httpx.get(f"{pypiserver}/{project_dir}", auth=(USER_NAME, USER_PASS), follow_redirects=True).text
    print(f"=== {pypiserver}/{project_dir}")
    print(package_state)

    # Test that expected artifacts are emitted
    project_file_name = project_dir.replace("-", "_").lower()
    if project_dir.startswith("rust-"):
        assert f"{project_file_name}-0.1.0-cp39-abi3-manylinux_2_34_x86_64" in package_state
    else:
        assert f"{project_file_name}-0.1.0-py3-none-any.whl" in package_state

    kraken_ctx.execute([":python.install"])
    # TODO (@NiklasRosenstein): Test importing the consumer project.


@unittest.mock.patch.dict(os.environ, {})
def test__python_project_upgrade_python_version_string(
    kraken_ctx: Context,
    kraken_project: Project,
) -> None:
    tempdir = kraken_project.directory

    build_as_version = "9.9.9a1"
    init_file = "src/version_project/__init__.py"
    original_dir = example_dir("version-project")
    project_dist = kraken_project.build_directory / "python-dist"

    # Copy the projects to the temporary directory.
    shutil.copytree(original_dir, tempdir, dirs_exist_ok=True)
    logger.info("Loading and executing Kraken project (%s)", tempdir)

    pyproject = TomlFile.read(original_dir / "pyproject.toml")
    local_build_system = python.buildsystem.detect_build_system(tempdir)
    assert local_build_system is not None
    assert local_build_system.get_pyproject_reader(pyproject) is not None
    assert local_build_system.get_pyproject_reader(pyproject).get_name() == "version-project"
    python.settings.python_settings(project=kraken_project, build_system=local_build_system)
    python.build(as_version=build_as_version, project=kraken_project)
    kraken_ctx.execute([":build"])

    # Check if files that were supposed to be temporarily modified are the same after the build.
    assert filecmp.cmp(original_dir / "pyproject.toml", tempdir / "pyproject.toml", shallow=False), (
        tempdir / "pyproject.toml"
    ).read_text()
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


@unittest.mock.patch.dict(os.environ, {})
def test__python_project__upgrade_relative_import_version(
    kraken_ctx: Context,
    kraken_project: Project,
) -> None:
    tempdir = kraken_project.directory

    build_as_version = "0.1.1"
    project_name = "uv-project-relative-import"
    original_dir = example_dir(project_name)
    project_dist = kraken_project.build_directory / "python-dist"

    # Copy the projects to the temporary directory.
    shutil.copytree(original_dir, tempdir, dirs_exist_ok=True)
    python.build(as_version=build_as_version, project=kraken_project)
    kraken_ctx.execute([":build"])

    # Check if generated files are named following proper version.
    formatted_project_name = project_name.replace("-", "_")
    assert Path(project_dist / f"{formatted_project_name}-{build_as_version}.tar.gz").is_file()
    assert Path(project_dist / f"{formatted_project_name}-{build_as_version}-py3-none-any.whl").is_file()
    with tarfile.open(project_dist / f"{formatted_project_name}-{build_as_version}.tar.gz", "r:gz") as tar:
        # Check if generated files store proper version.
        metadata_file = tar.extractfile(f"{formatted_project_name}-{build_as_version}/PKG-INFO")
        assert metadata_file is not None, ".tar.gz file does not contain an 'PKG-INFO'"
        metadata = metadata_file.read().decode("UTF-8")
        assert f"Requires-Dist: uv-project=={build_as_version}" in metadata
        assert f"Requires-Dist: uv-project=={build_as_version}; extra == 'opt'" in metadata


M = TypeVar("M", PdmPyprojectHandler, PoetryPyprojectHandler)


@pytest.mark.parametrize(
    "project_dir, reader, expected_python_version",
    [
        ("poetry-project", PoetryPyprojectHandler, "^3.7"),
        ("slap-project", PoetryPyprojectHandler, "^3.6"),
        ("pdm-project", PdmPyprojectHandler, ">=3.9"),
        ("rust-poetry-project", MaturinPoetryPyprojectHandler, "^3.9"),
        ("uv-project", UvPyprojectHandler, ">=3.10"),
    ],
)
@unittest.mock.patch.dict(os.environ, {})
def test__python_pyproject_reads_correct_data(
    project_dir: str,
    reader: type[M],
    expected_python_version: str,
    kraken_project: Project,
) -> None:
    # Copy the projects to the temporary directory.
    new_dir = kraken_project.directory / project_dir
    shutil.copytree(example_dir(project_dir), new_dir)

    pyproject = TomlFile.read(new_dir / "pyproject.toml")
    local_build_system = python.buildsystem.detect_build_system(new_dir)
    assert local_build_system is not None
    assert local_build_system.get_pyproject_reader(pyproject) is not None
    assert local_build_system.get_pyproject_reader(pyproject).get_name() == project_dir
    assert local_build_system.get_pyproject_reader(pyproject).get_python_version_constraint() == expected_python_version

    spec = reader(pyproject)

    assert spec.get_name() == project_dir
    assert spec.get_python_version_constraint() == expected_python_version


@unittest.mock.patch.dict(os.environ, {})
def test__python_project_coverage(
    kraken_ctx: Context,
    kraken_project: Project,
) -> None:
    os.environ["PYTEST_FLAGS"] = ""

    tempdir = kraken_project.directory
    original_dir = example_dir("slap-project")

    # Copy the projects to the temporary directory.
    shutil.copytree(original_dir, tempdir, dirs_exist_ok=True)
    logger.info("Loading and executing Kraken project (%s)", tempdir)

    pyproject = TomlFile.read(original_dir / "pyproject.toml")
    local_build_system = python.buildsystem.detect_build_system(tempdir)
    assert local_build_system is not None
    assert local_build_system.get_pyproject_reader(pyproject) is not None
    assert local_build_system.get_pyproject_reader(pyproject).get_name() == "slap-project"

    python.settings.python_settings(project=kraken_project, build_system=local_build_system)
    python.pytest(project=kraken_project, coverage=python.CoverageFormat.XML)
    python.install(project=kraken_project)
    python.build(project=kraken_project)
    kraken_ctx.execute([":build", ":test"])

    assert Path(kraken_project.build_directory / "coverage.xml").is_file()


def test__python_project_can_lint_lint_enforced_directories(
    kraken_ctx: Context,
    kraken_project: Project,
) -> None:
    tempdir = kraken_project.directory
    original_dir = example_dir("lint-enforced-directories-project")

    shutil.copytree(original_dir, tempdir, dirs_exist_ok=True)
    logger.info("Loading and executing Kraken project (%s)", tempdir)

    python.settings.python_settings(
        project=kraken_project, lint_enforced_directories=[tempdir / "examples", tempdir / "bin"]
    )
    python.install(project=kraken_project)

    for linter, version in {
        "black": "23.12.1",
        "flake8": "6.1.0",
        "isort": "5.13.2",
        "mypy": "1.8.0",
        "pycln": "2.4.0",
        "pylint": "3.0.3",
    }.items():
        getattr(python, linter)(project=kraken_project, version_spec=f"=={version}")

    kraken_ctx.execute([":lint"])
