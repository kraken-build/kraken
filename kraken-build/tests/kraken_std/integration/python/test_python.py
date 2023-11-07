import filecmp
import logging
import os
import shutil
import tarfile
import unittest.mock
from pathlib import Path
from typing import TypeVar

import pytest
import tomli
from tests.util.docker import DockerServiceManager

from kraken.common import not_none
from kraken.core import Context, Project
from kraken.std import python
from kraken.std.python.buildsystem.maturin import MaturinPoetryPyprojectHandler
from kraken.std.python.buildsystem.pdm import PdmPyprojectHandler
from kraken.std.python.buildsystem.poetry import PoetryPyprojectHandler
from kraken.std.python.pyproject import Pyproject

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
        ["--passwords", "/.htpasswd", "-a", "update", "--hash-algo", "sha256"],
        ports=[f"{PYPISERVER_PORT}:8080"],
        volumes=[f"{htpasswd.absolute()}:/.htpasswd"],
        detach=True,
        probe=("GET", index_url),
    )
    logger.info("Started local Pypiserver at %s", index_url)
    return index_url


@pytest.mark.parametrize(
    "project_dir",
    ["poetry-project", "slap-project", "pdm-project", "rust-poetry-project", "rust-pdm-project"],
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

    # NOTE: The Slap project doesn't need an apply because we don't write the package index into the pyproject.toml.
    kraken_ctx.execute([":apply"])

    kraken_ctx.execute([":python.install"])
    # TODO (@NiklasRosenstein): Test importing the consumer project.


@unittest.mock.patch.dict(os.environ, {})
def test__python_project_upgrade_python_version_string(
    kraken_ctx: Context,
    kraken_project: Project,
) -> None:
    tempdir = kraken_project.directory

    project_dir = "version-project"
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
        ("rust-poetry-project", MaturinPoetryPyprojectHandler, "^3.7"),
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
    shutil.copytree(Path(__file__).parent / "data" / project_dir, new_dir)

    pyproject = Pyproject.read(new_dir / "pyproject.toml")
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
    tempdir = kraken_project.directory

    project_dir = "slap-project"
    original_dir = Path(__file__).parent / "data" / project_dir

    # Copy the projects to the temporary directory.
    shutil.copytree(original_dir, tempdir, dirs_exist_ok=True)
    logger.info("Loading and executing Kraken project (%s)", tempdir)

    pyproject = Pyproject.read(original_dir / "pyproject.toml")
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


def test__python_project_can_lint_lint_enforced_directories(kraken_ctx: Context, kraken_project: Project) -> None:
    tempdir = kraken_project.directory

    project_dir = "lint-enforced-directories-project"
    original_dir = Path(__file__).parent / "data" / project_dir

    shutil.copytree(original_dir, tempdir, dirs_exist_ok=True)
    logger.info("Loading and executing Kraken project (%s)", tempdir)

    python.settings.python_settings(
        project=kraken_project, lint_enforced_directories=[tempdir / "examples", tempdir / "bin"]
    )
    for linter in ["black", "flake8", "isort", "mypy", "pycln", "pylint"]:
        getattr(python, linter)(project=kraken_project)

    kraken_ctx.execute([":lint"])
