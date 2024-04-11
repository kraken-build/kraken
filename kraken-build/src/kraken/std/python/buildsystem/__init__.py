""" Abstraction of Python build systems such as Poetry and Slap. """


from __future__ import annotations

import abc
import contextlib
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from kraken.core import TaskStatus
from kraken.std.python.buildsystem.helpers import update_python_version_str_in_source_files
from kraken.std.python.pyproject import Pyproject, PyprojectHandler

if TYPE_CHECKING:
    from ..settings import PythonSettings

logger = logging.getLogger(__name__)


class PythonBuildSystem(abc.ABC):
    """Abstraction of a Python build system."""

    name: ClassVar[str]
    project_directory: Path

    @abc.abstractmethod
    def supports_managed_environments(self) -> bool:
        """Return `True` if the build system supports managed environments."""

    @abc.abstractmethod
    def get_managed_environment(self) -> ManagedEnvironment:
        """Return a handle for the managed environment.

        :raise NotImplementedError: If :meth:`supports_managed_environment` returns `False`.
        """

    def update_pyproject(self, settings: PythonSettings, pyproject: Pyproject) -> None:
        """A chance to permanently update the Pyproject configuration."""

        handler = self.get_pyproject_reader(pyproject)
        package_sources = [x for x in settings.package_indexes.values() if x.is_package_source]
        if package_sources:
            try:
                handler.set_package_indexes(package_sources)
            except NotImplementedError:
                logger.debug("build system %r does not support managing package indexes", self.name)

    @abc.abstractmethod
    def update_lockfile(self, settings: PythonSettings, pyproject: Pyproject) -> TaskStatus:
        """Resolve all dependencies of the project and write the exact versions into
        the correspondig lock file. In the case of Poetry it is poetry.lock."""

    @abc.abstractmethod
    def requires_login(self) -> bool:
        """Return True if this build system requires a separate login step (i.e. if the credentials cannot be
        passed at install time to the command-line)."""

    def login(self, settings: PythonSettings) -> None:
        """Log into the Python package indices."""

        raise NotImplementedError

    @contextlib.contextmanager
    def bump_version(self, version: str) -> Iterator[None]:
        """Set the version of the project temporarily.

        The default implementation bumps the version number in the `pyproject.toml` using `get_pyproject_reader()`
        as well as in the source files in the packages provided by the `PyprojectHandler.get_packages()`.
        """

        # Save the previous version of the pyproject.toml.
        pyproject_toml = self.project_directory / "pyproject.toml"

        revert_files: dict[Path, str] = {}
        revert_files[pyproject_toml] = pyproject_toml.read_text()

        # Bump the in-source version number.
        pyproject = self.get_pyproject_reader(Pyproject.read(pyproject_toml))
        try:
            pyproject.set_path_dependencies_to_version(version)
        except NotImplementedError:
            pass
        pyproject.set_version(version)
        pyproject.raw.save()

        for package in pyproject.get_packages():
            package_dir = self.project_directory / (package.from_ or "") / package.include

            sum_replaced = 0
            for path, n_replaced in update_python_version_str_in_source_files(version, package_dir):
                sum_replaced += n_replaced
                revert_files[path] = path.read_text()

            if sum_replaced > 0:
                print(
                    f"Bumped {sum_replaced} version reference(s) in {len(revert_files)} files(s) in directory",
                    f"{package_dir.relative_to(self.project_directory)} to {version}",
                )

        print("Modified files:")
        for path in sorted(revert_files):
            print("  -", path)

        try:
            yield
        finally:
            for path, content in revert_files.items():
                path.write_text(content)

    @abc.abstractmethod
    def build(self, output_directory: Path) -> list[Path]:
        """Build one or more distributions of the project managed by this build system.

        :param output_directory: The directory where the distributions should be placed.
        """

    @abc.abstractmethod
    def get_pyproject_reader(self, pyproject: Pyproject) -> PyprojectHandler:
        """Return an object able to read the pyproject file depending on the build system."""

    @abc.abstractmethod
    def get_lockfile(self) -> Path | None:
        """Return the lockfile specific to this buildsystem, or None if not supported."""


class ManagedEnvironment(abc.ABC):
    """Abstraction of a managed Python environment."""

    @abc.abstractmethod
    def exists(self) -> bool:
        """Return `True` if the managed environment exists."""

    @abc.abstractmethod
    def get_path(self) -> Path:
        """Return the path to the managed environment.

        :raises RuntimeError: May be raised if the environment does not exist (it may not be possible to
            determine the path of the environment before it exists depending on the build system).
        """

    @abc.abstractmethod
    def install(self, settings: PythonSettings) -> None:
        """Install the managed environment. This should be a no-op if the environment already exists."""

    def always_install(self) -> bool:
        """Always trigger environment installation even if already exists"""
        return False


def detect_build_system(project_directory: Path) -> PythonBuildSystem | None:
    """Detect the Python build system used in *project_directory*."""

    pyproject_toml = project_directory / "pyproject.toml"
    if not pyproject_toml.is_file():
        return None

    pyproject_content = pyproject_toml.read_text()

    if "[tool.slap]" in pyproject_content:
        from .slap import SlapPythonBuildSystem

        return SlapPythonBuildSystem(project_directory)

    if "poetry-core" in pyproject_content:
        from .poetry import PoetryPythonBuildSystem

        return PoetryPythonBuildSystem(project_directory)

    if "maturin" in pyproject_content:
        if "[tool.poetry]" in pyproject_content:
            from .maturin import MaturinPoetryPythonBuildSystem

            return MaturinPoetryPythonBuildSystem(project_directory)
        else:
            from .maturin import MaturinPdmPythonBuildSystem

            return MaturinPdmPythonBuildSystem(project_directory)

    if "pdm" in pyproject_content:
        from .pdm import PDMPythonBuildSystem

        return PDMPythonBuildSystem(project_directory)

    return None
