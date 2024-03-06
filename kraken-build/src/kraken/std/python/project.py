""" New-style API and template for defining the tasks for an entire Python project."""

import logging
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from nr.stream import Optional

from kraken.std.git.version import EmptyGitRepositoryError, GitVersion, NotAGitRepositoryError, git_describe
from kraken.std.python.buildsystem import detect_build_system
from kraken.std.python.pyproject import PackageIndex
from kraken.std.python.settings import python_settings
from kraken.std.python.tasks.pytest_task import CoverageFormat
from kraken.std.python.version import git_version_to_python_version

logger = logging.getLogger(__name__)


def python_package_index(
    *,
    alias: str,
    index_url: str | None = None,
    upload_url: str | None = None,
    credentials: tuple[str, str] | None = None,
    is_package_source: bool = True,
    priority: PackageIndex.Priority | str = PackageIndex.Priority.supplemental,
    publish: bool = False,
) -> None:
    """
    Add a Python package index that can be used to consume packages and/or to publish Python packages to.

    Args:
        alias: An alias for the package index. If no *index_url* is specified, it must be either `pypi` or `testpypi`
            to refer to `pypi.org` and `test.pypi.org`, respectively.
        index_url: The URL of the package index, incl. the trailing `/simple` portion.
        upload_url: For some Python registries, the upload URL differs from the index URL, often without `/simple`.
            If it is not specified, the *index_url* must end with `/simple` and the suffix will be removed to
            derive the *upload_url*.
        credentials: Username/password to read/write to the package index, if needed.
        is_package_source: Whether this package index should be considered as a source for packages when resolving
            the dependencies of the project. Kraken will inject these settings into the `pyproject.toml` in the section
            corresponding to the Python build system being used (e.g. Poetry or PDM) when running `krakenw run apply`.
        priority: The package priority. This is inspired by Poetry and may not be fully applicable to other Python
            build systems. Kraken does a best-effort to translate the priority for the corresponding build system.
        publish: Whether a publish task for the package registry should be created. The publish task will be called
            `python.publish.{alias}`.
    """

    # NOTE(@niklas): Currently this function is a simple wrapper, but it may replace the wrapped method eventually.

    from .settings import python_settings

    python_settings().add_package_index(
        alias=alias,
        index_url=index_url,
        upload_url=upload_url,
        credentials=credentials,
        is_package_source=is_package_source,
        priority=priority,
        publish=publish,
    )


def python_project(
    *,
    source_directory: str = "src",
    tests_directory: str = "tests",
    additional_lint_directories: Sequence[str] | None = None,
    exclude_lint_directories: Sequence[str] = (),
    line_length: int = 120,
    enforce_project_version: str | None = None,
    detect_git_version_build_type: Literal["release", "develop", "branch"] = "develop",
    pyupgrade_keep_runtime_typing: bool = False,
    pycln_remove_all_unused_imports: bool = False,
    pytest_ignore_dirs: Sequence[str] = (),
    mypy_use_daemon: bool = True,
    isort_version_spec: str = ">=5.13.2,<6.0.0",
    black_version_spec: str = ">=24.1.1,<25.0.0",
    flake8_version_spec: str = ">=7.0.0,<8.0.0",
    flake8_additional_requirements: Sequence[str] = (),
    flake8_extend_ignore: Sequence[str] = ("W503", "W504", "E203", "E704"),
    mypy_version_spec: str = ">=1.8.0,<2.0.0",
    pycln_version_spec: str = ">=2.4.0,<3.0.0",
    pyupgrade_version_spec: str = ">=3.15.0,<4.0.0",
) -> None:
    """
    Use this function in a Python project.

    The Python build system used for the library is automatically detected. Supported build systems are:

    * [Slap](https://github.com/NiklasRosenstein/slap)
    * [Poetry](https://python-poetry.org/docs)
    * [PDM](https://pdm-project.org/latest/)

    Note: Pytest dependencies
        Your project should have the `pytest` dependency in it's development dependencies. Kraken does not currently
        automatically inject this dependency into your project. If you would like to utilize parallel test execution,
        you should also add `pytest-xdist[psutil]`. Unlike linters and formatters, Pytest needs to be available at
        runtime in the Python environment that the tests are being run in, so Kraken cannot install it separately with
        Pex.

    Args:
        source_directory: The directory that contains all Python source files.
        tests_directory: The directory that contains test files that are not in the source directory.
        additional_lint_directories: Additional directories in the project that contain Python source code
            that should be linted and formatted. If not specified, it will default to `["examples"]` if the
            directory exists.
        exclude_lint_directories: Directories in the project that contain Python sourec code that should not be
            linted and formatted but would otherwise be included via *source_directory*, *tests_directory*
            and *additional_directories*.
        line_length: The line length to assume for all formatters and linters.
        enforce_project_version: When set, enforces the specified version number for the project when building wheels
            and publishing them. If not specified, the version number will be derived from the Git repository using
            `git describe --tags`.
        detect_git_version_build_type: When specified, this influences the version number that will be automatically
            generated when `enforce_project_version` is not set. When set to `"release"`, the current commit in
            the Git repository must have exactly one tag associated with it. When set to `"develop"` (the default),
            the version number will be derived from the most recent tag and the distance to the current commit. If
            the current commit is tagged, the version number will be the tag name anyway. When set to `"branch"`, the
            version number will be derived from the distance to the most recent tag and include the SHA of the commit.
        pyupgrade_keep_runtime_typing: Whether to not replace `typing` type hints. This is required for example
            for projects using Typer as it does not support all modern type hints at runtime.
        pycln_remove_all_unused_imports: Remove all unused imports, including these with side effects.
            For reference, see https://hadialqattan.github.io/pycln/#/?id=-a-all-flag.
        flake8_additional_requirements: Additional Python requirements to install alongside Flake8. This should
            be used to add Flake8 plugins.
        flake8_extend_ignore: Flake8 lints to ignore. The default ignores lints that would otherwise conflict with
            the way Black formats code.
    """

    from kraken.build import project
    from kraken.common import not_none

    from .pyproject import Pyproject
    from .tasks.black_task import BlackConfig, black as black_tasks
    from .tasks.build_task import build as build_task
    from .tasks.flake8_task import Flake8Config, flake8 as flake8_tasks
    from .tasks.info_task import info as info_task
    from .tasks.install_task import install as install_task
    from .tasks.isort_task import IsortConfig, isort as isort_tasks
    from .tasks.login_task import login as login_task
    from .tasks.mypy_task import MypyConfig, mypy as mypy_task
    from .tasks.publish_task import publish as publish_task
    from .tasks.pycln_task import pycln as pycln_task
    from .tasks.pytest_task import pytest as pytest_task
    from .tasks.pyupgrade_task import pyupgrade as pyupgrade_task
    from .tasks.update_lockfile_task import update_lockfile_task
    from .tasks.update_pyproject_task import update_pyproject_task

    if additional_lint_directories is None:
        additional_lint_directories = []
        if project.directory.joinpath("examples").is_dir():
            additional_lint_directories.append("examples")

    source_paths = [source_directory, *additional_lint_directories]
    if project.directory.joinpath(tests_directory).is_dir():
        source_paths.insert(1, tests_directory)
    logger.info("Source paths for Python project %s: %s", project.address, source_paths)

    build_system = not_none(detect_build_system(project.directory))
    pyproject = Pyproject.read(project.directory / "pyproject.toml")
    handler = build_system.get_pyproject_reader(pyproject)
    # project_version = handler.get_version()

    # NOTE(@niklas): This is not entirely correct, but good enough in practice. We assume that for a version range,
    #       the lowest Python version comes first in the version spec. We also need to support Poetry-style semver
    #       range selectors here.
    if python_version := handler.get_python_version_constraint():
        python_version = Optional(re.search(r"[\d\.]+", python_version)).map(lambda m: m.group(0)).or_else(None)
    if not python_version:
        logger.warning(
            "Unable to determine minimum Python version for project %s, fallback to '3'",
            project.directory,
        )
        python_version = "3"

    login_task()
    update_lockfile_task()
    update_pyproject_task()
    install_task()
    info_task(build_system=build_system)

    pyupgrade_task(
        python_version=python_version,
        keep_runtime_typing=pyupgrade_keep_runtime_typing,
        exclude=[Path(x) for x in exclude_lint_directories],
        paths=source_paths,
        version_spec=pyupgrade_version_spec,
    )

    pycln_task(
        paths=source_paths,
        exclude_directories=exclude_lint_directories,
        remove_all_unused_imports=pycln_remove_all_unused_imports,
        version_spec=pycln_version_spec,
    )

    black = black_tasks(
        paths=source_paths,
        config=BlackConfig(line_length=line_length, exclude_directories=exclude_lint_directories),
        version_spec=black_version_spec,
    )

    isort = isort_tasks(
        paths=source_paths,
        config=IsortConfig(
            profile="black",
            line_length=line_length,
            extend_skip=exclude_lint_directories,
        ),
        version_spec=isort_version_spec,
    )
    isort.format.depends_on(black.format)

    flake8 = flake8_tasks(
        paths=source_paths,
        config=Flake8Config(
            max_line_length=line_length, extend_ignore=flake8_extend_ignore, exclude=exclude_lint_directories
        ),
        version_spec=flake8_version_spec,
        additional_requirements=flake8_additional_requirements,
    )
    flake8.depends_on(black.format, isort.format, mode="order-only")

    mypy_task(
        paths=source_paths,
        config=MypyConfig(
            mypy_path=[source_directory],
            exclude_directories=exclude_lint_directories,
            global_overrides={},
            module_overrides={},
        ),
        version_spec=mypy_version_spec,
        python_version=python_version,
        use_daemon=mypy_use_daemon,
    )

    # TODO(@niklas): Improve this heuristic to check whether Coverage reporting should be enabled.
    if "pytest-cov" in str(dict(pyproject)):
        coverage = CoverageFormat.XML
    else:
        coverage = None

    pytest_task(
        paths=source_paths,
        ignore_dirs=pytest_ignore_dirs,
        coverage=coverage,
        doctest_modules=True,
        allow_no_tests=True,
    )

    if not enforce_project_version:
        try:
            git_version = GitVersion.parse(git_describe(project.directory))
        except NotAGitRepositoryError:
            logger.info("No Git repository found in %s, not enforcing a project version", project.directory)
            enforce_project_version = None
        except EmptyGitRepositoryError:
            logger.info("Empty Git repository found in %s, not enforcing a project version", project.directory)
            enforce_project_version = None
        else:
            match detect_git_version_build_type:
                case "release" | "develop":
                    if (
                        detect_git_version_build_type == "release"
                        and git_version.distance
                        and git_version.distance.value > 0
                    ):
                        raise ValueError(
                            f"Git version for project {project.directory} is not a release version: {git_version}"
                        )
                    enforce_project_version = git_version_to_python_version(git_version)
                case "branch":
                    enforce_project_version = git_version_to_python_version(git_version, include_sha=True)

    if enforce_project_version:
        logger.info("Enforcing version %s for project %s", enforce_project_version, project.directory)

    # Create publish tasks for any package index with publish=True.
    build = build_task(as_version=enforce_project_version)
    for index in python_settings().package_indexes.values():
        if index.publish:
            publish_task(package_index=index.alias, distributions=build.output_files, interactive=False)

    # TODO(@niklas): Support auto-detecting when Mypy stubtests need to be run or
    #       accept arguments for stubtests.
