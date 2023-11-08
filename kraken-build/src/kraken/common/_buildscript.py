import enum
from concurrent.futures import Future
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import local
from typing import Any, Callable, Iterator, List, Sequence

import builddsl


@dataclass
class BuildscriptMetadata:
    """
    Metadata for a Kraken build and its runtime environment.
    """

    index_url: "str | None" = None
    extra_index_urls: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    additional_sys_paths: List[str] = field(default_factory=list)

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
    closure: "builddsl.UnboundClosure | None" = None,
    *,
    index_url: "str | None" = None,
    extra_index_urls: "Sequence[str] | None" = None,
    requirements: "Sequence[str] | None" = None,
    additional_sys_paths: "Sequence[str] | None" = None,
) -> BuildscriptMetadata:
    """
    This function creates a :class:`BuildscriptMetadata` object and returns it.

    When called from inside the context of :meth:`BuildscriptMetadata.capture()`, the function raises a
    :class:`BuildscriptMetadataException` instead.
    """

    metadata = BuildscriptMetadata(
        index_url=index_url,
        extra_index_urls=list(extra_index_urls or ()),
        requirements=list(requirements or ()),
        additional_sys_paths=list(additional_sys_paths or ()),
    )

    if closure:
        closure(metadata)

    if _global.mode == _Mode.RAISE:
        raise BuildscriptMetadataException(metadata)
    elif _global.mode == _Mode.CALLBACK:
        assert _global.func is not None
        _global.func(metadata)

    return metadata
