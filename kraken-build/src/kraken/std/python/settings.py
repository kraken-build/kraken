from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from kraken.core import Project
from kraken.std.python.pyproject import PackageIndex

from .buildsystem import PythonBuildSystem, detect_build_system

logger = logging.getLogger(__name__)


@dataclass
class PythonSettings:
    """Project-global settings for Python tasks."""

    @dataclass
    class _PackageIndex(PackageIndex):
        """
        Extends the #PackageIndex with additional fields we need for Python package indexes at runtime in Kraken.
        """

        #: An alternative URL to upload packages to.
        upload_url: str | None

        #: Credentials to use when publishing to or reading from the index.
        credentials: tuple[str, str] | None

        #: Whether this index should be used to source packages from.
        is_package_source: bool

        #: Whether this index should be used to publish packages to.
        publish: bool

    project: Project
    build_system: PythonBuildSystem | None = None
    source_directory: Path = Path("src")
    tests_directory: Path | None = None
    lint_enforced_directories: list[Path] = field(default_factory=list)
    package_indexes: dict[str, _PackageIndex] = field(default_factory=dict)
    always_use_managed_env: bool = True
    skip_install_if_venv_exists: bool = True

    def get_tests_directory(self) -> Path | None:
        """Returns :attr:`tests_directory` if it is set. If not, it will look for the following directories and
        return the first that exists: `test/`, `tests/`, `src/test/`, `src/tests/`. The determined path will be
        relative to the project directory."""

        if self.tests_directory and self.tests_directory.is_dir():
            return self.tests_directory
        for test_dir in map(Path, ["test", "tests", "src/test", "src/tests"]):
            if (self.project.directory / test_dir).is_dir():
                return test_dir
        return None

    def get_tests_directory_as_args(self) -> list[str]:
        """Returns a list with a single item that is the test directory, or an empty list. This is convenient
        when constructing command-line arguments where you want to pass the test directory if it exists."""

        test_dir = self.get_tests_directory()
        return [] if test_dir is None else [str(test_dir)]

    def get_default_package_index(self) -> _PackageIndex | None:
        return next(
            (
                index
                for index in self.package_indexes.values()
                if index.priority.value == PackageIndex.Priority.default.value
            ),
            None,
        )

    def add_package_index(
        self,
        alias: str,
        *,
        index_url: str | None = None,
        upload_url: str | None = None,
        credentials: tuple[str, str] | None = None,
        is_package_source: bool = True,
        priority: PackageIndex.Priority | str = PackageIndex.Priority.supplemental,
        publish: bool = False,
    ) -> PythonSettings:
        """Adds an index to consume Python packages from or publish packages to.

        :param alias: An alias for the package index.
        :param index_url: The URL of the package index (with the trailing `/simple` bit if applicable).
            If not specified, *alias* must be a known package index (`pypi` or `testpypi`).
        :param upload_url: If the upload url deviates from the registry URL. Otherwise, the upload URL will
            be the same as the *url*,
        :param credentials: Optional credentials to read from the index.
        :param is_package_source: If set to `False`, the index will not be used to source packages from, but
            can be used to publish to.
        :param publish: Whether publishing to this index should be enabled.
        """

        if isinstance(priority, str):
            priority = PackageIndex.Priority[priority]

        if priority == PackageIndex.Priority.default:
            defidx = self.get_default_package_index()
            if defidx is not None and defidx.alias != alias:
                raise ValueError(f"cannot add another default index (got: {defidx.alias!r}, trying to add: {alias!r})")

        if index_url is None:
            if alias == "pypi":
                index_url = "https://pypi.org/simple"
            elif alias == "testpypi":
                index_url = "https://test.pypi.org/simple"
            else:
                raise ValueError(f"cannot derive index URL for alias {alias!r}")
        if upload_url is None:
            if alias == "pypi":
                upload_url = "https://upload.pypi.org/legacy"
            elif alias == "testpypi":
                upload_url = "https://test.pypi.org/legacy"
            elif index_url.endswith("/simple"):
                upload_url = index_url[: -len("/simple")]
            elif index_url.endswith("/simple/"):
                upload_url = index_url[: -len("/simple/")]
            else:
                raise ValueError(f"cannot derive upload URL for alias {alias!r} and index URL {index_url!r}")

        self.package_indexes[alias] = self._PackageIndex(
            alias=alias,
            index_url=index_url,
            priority=priority,
            upload_url=upload_url,
            credentials=credentials,
            is_package_source=is_package_source,
            publish=publish,
            verify_ssl=True,
        )
        return self

    def get_primary_index(self) -> _PackageIndex | None:
        default: PythonSettings._PackageIndex | None = None
        for idx in self.package_indexes.values():
            if idx.priority == PackageIndex.Priority.primary:
                return idx
            if idx.priority == PackageIndex.Priority.default:
                default = idx
        return default


def python_settings(
    project: Project | None = None,
    build_system: PythonBuildSystem | None = None,
    source_directory: str | Path | None = None,
    tests_directory: str | Path | None = None,
    lint_enforced_directories: list[str | Path] | None = None,
    always_use_managed_env: bool | None = None,
    skip_install_if_venv_exists: bool | None = None,
) -> PythonSettings:
    """Read the Python settings for the given or current project and optionally update attributes.

    :param project: The project to get the settings for. If not specified, the current project will be used.
    :environment_handler: If specified, set the :attr:`PythonSettings.environment_handler`. If a string is specified,
        the following values are currently supported: `"poetry"`.
    :param source_directory: The source directory. Defaults to `"src"`.
    :param tests_directory: The tests directory. Automatically determined if left empty.
    :param lint_enforced_directories: Any extra directories containing Python files, e.g. bin/, scripts/, and
        examples/, to be linted alongside the source and tests directories.
    """

    project = project or Project.current()
    settings = project.find_metadata(PythonSettings)
    if settings is None:
        settings = PythonSettings(project)
        project.metadata.append(settings)

    if build_system is None and settings.build_system is None:
        # Autodetect the environment handler.
        build_system = detect_build_system(project.directory)
        if build_system:
            logger.info("Detected Python build system %r for %s", type(build_system).__name__, project)

    if build_system is not None:
        if settings.build_system:
            logger.warning(
                "overwriting existing PythonSettings.environment_handler=%r with %r",
                settings.build_system,
                build_system,
            )
        settings.build_system = build_system

    if source_directory is not None:
        settings.source_directory = Path(source_directory)

    if tests_directory is not None:
        settings.tests_directory = Path(tests_directory)

    if lint_enforced_directories is not None:
        dirs = []
        for directory in lint_enforced_directories:
            directory_path = Path(directory)
            if not directory_path.exists():
                logger.debug(f"skipping specified lint enforced directory {directory_path} as it does not exist")
            elif not directory_path.is_dir():
                logger.warning(f"skipping specified lint enforced directory {directory_path} as it is not a directory")
            else:
                dirs.append(directory_path)
        settings.lint_enforced_directories = dirs

    if always_use_managed_env is not None:
        settings.always_use_managed_env = True

    if skip_install_if_venv_exists is not None:
        settings.skip_install_if_venv_exists = skip_install_if_venv_exists

    return settings
