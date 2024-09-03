import enum
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import Future
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import local
from typing import Any


@dataclass
class BuildscriptMetadata:
    """
    Metadata for a Kraken build and its runtime environment.
    """

    index_url: "str | None" = None
    extra_index_urls: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    additional_sys_paths: list[str] = field(default_factory=list)
    interpreter_constraint: str | None = None

    def requires(self, requirement: str) -> None:
        self.requirements.append(requirement)

    def extra_index_url(self, url: str) -> None:
        self.extra_index_urls.append(url)

    def additional_sys_path(self, path: str) -> None:
        self.additional_sys_paths.append(path)

    @staticmethod
    @contextmanager
    def capture() -> Iterator["Future[BuildscriptMetadata]"]:
        """
        A context manager that will ensure calling :func:`buildscript` will raise a
        :class:`BuildscriptMetadataException` and catch that exception to return the metadata.

        This is used to retrieve the metadata in Kraken wrapper.
        """

        future: "Future[BuildscriptMetadata]" = Future()
        _global.mode = _Mode.RAISE
        try:
            yield future
        except BuildscriptMetadataException as exc:
            future.set_result(exc.metadata)
        else:
            exception = RuntimeError("No KrakenMetadataException was raised, did metadata() get called?")
            future.set_exception(exception)
            raise exception
        finally:
            _global.mode = _Mode.PASSTHROUGH

    @staticmethod
    @contextmanager
    def callback(func: Callable[["BuildscriptMetadata"], Any]) -> Iterator[None]:
        """
        A context manager that will ensure calling the given *func* after :func:`buildscript` is run.

        This is used to retrieve and react upon the metadata in the Kraken build system.
        """

        _global.mode = _Mode.CALLBACK
        _global.func = func
        try:
            yield
        finally:
            _global.mode = _Mode.PASSTHROUGH
            _global.func = None


class BuildscriptMetadataException(BaseException):
    """
    This exception is raised by the :func:`metadata` function.
    """

    def __init__(self, metadata: BuildscriptMetadata) -> None:
        self.metadata = metadata

    def __str__(self) -> str:
        return (
            "If you are seeing this message, something has gone wrong with catching the exception. This "
            "exception is used to abort and transfer Kraken metadata to the caller."
        )


class _Mode(enum.Enum):
    PASSTHROUGH = 0
    RAISE = 1
    CALLBACK = 2


class _ModeGlobal(local):
    mode: _Mode = _Mode.PASSTHROUGH
    func: "Callable[[BuildscriptMetadata], Any] | None" = None


_global = _ModeGlobal()


def buildscript(
    *,
    index_url: "str | None" = None,
    extra_index_urls: "Sequence[str] | None" = None,
    requirements: "Sequence[str] | None" = None,
    additional_sys_paths: "Sequence[str] | None" = None,
    interpreter_constraint: str | None = None,
) -> BuildscriptMetadata:
    """
    Use this function to the dependencies and additional install options for the build environment of your Kraken
    build script that is installed and managed by Kraken-wrapper. This function must be called at the very beginning
    of your `.kraken.py` build script at the root of your project.

    __Example:__

    ```py
    from kraken.common import buildscript
    buildscript(
        requirements=["kraken-build"],
    )

    from kraken.std import ...
    ```

    You can depend on local dependencies and Python packages from URLs by prefixing them with `<package name> @`:

    ```py
    buildscript(requirements=[
        "kraken-build @ git+https://github.com/kraken-build/kraken.git@nr/python-project#subdirectory=kraken-build"
    ])
    ```

    Args:
        index_url: The index URL for Python packages to install from. If this is a private package registry, the
            credentials can be configured with the `krakenw auth` command.
        extra_index_urls: Additional index URLs for Python packages to install from.
        requirements: A list of Python package requirements to install. This usually contains at least `kraken-build`
            or some internal extension module that in turn depends on `kraken-build`.
        additional_sys_paths: Additional system paths to add to the Python environment.
        interpreter_constraint: Constraints for the Python interpreter that the build must be run with.
    """

    from kraken.core import Project

    if (project := Project.current(None)) and project != project.context.root_project:
        raise RuntimeError("buildscript() should be called only from the root project")

    metadata = BuildscriptMetadata(
        index_url=index_url,
        extra_index_urls=list(extra_index_urls or ()),
        requirements=list(requirements or ()),
        additional_sys_paths=list(additional_sys_paths or ()),
        interpreter_constraint=interpreter_constraint,
    )

    if _global.mode == _Mode.RAISE:
        raise BuildscriptMetadataException(metadata)
    elif _global.mode == _Mode.CALLBACK:
        assert _global.func is not None
        _global.func(metadata)

    return metadata
