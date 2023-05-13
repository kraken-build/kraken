from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

from kraken.core.api import Project

from .buildsystem import PythonBuildSystem, detect_build_system

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PythonIndex:
    alias: str
    index_url: str
    upload_url: str | None
    credentials: tuple[str, str] | None
    is_package_source: bool
    default: bool
    publish: bool


@dataclasses.dataclass
class PythonSettings:
    """Project-global settings for Python tasks."""

    project: Project
    build_system: PythonBuildSystem | None = None
    source_directory: Path = Path("src")
    tests_directory: Path | None = None
    package_indexes: dict[str, PythonIndex] = dataclasses.field(default_factory=dict)
    always_use_managed_env: bool = True

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

    def get_default_package_index(self) -> PythonIndex | None:
        return next((index for index in self.package_indexes.values() if index.default), None)

    def add_package_index(
        self,
        alias: str,
        *,
        index_url: str | None = None,
        upload_url: str | None = None,
        credentials: tuple[str, str] | None = None,
        is_package_source: bool = True,
        default: bool = False,
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

        if default:
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
            else:
                raise ValueError(f"cannot derive upload URL for alias {alias!r} and index URL {index_url!r}")

        self.package_indexes[alias] = PythonIndex(
            alias=alias,
            index_url=index_url,
            upload_url=upload_url,
            credentials=credentials,
            is_package_source=is_package_source,
            default=default,
            publish=publish,
        )
        return self


def python_settings(
    project: Project | None = None,
    build_system: PythonBuildSystem | None = None,
    source_directory: str | Path | None = None,
    tests_directory: str | Path | None = None,
    always_use_managed_env: bool | None = None,
) -> PythonSettings:
    """Read the Python settings for the given or current project and optionally update attributes.

    :param project: The project to get the settings for. If not specified, the current project will be used.
    :environment_handler: If specified, set the :attr:`PythonSettings.environment_handler`. If a string is specified,
        the following values are currently supported: `"poetry"`.
    :param source_directory: The source directory. Defaults to `"src"`.
    :param tests_directory: The tests directory. Automatically determined if left empty.
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

    if always_use_managed_env is not None:
        settings.always_use_managed_env = True

    return settings
