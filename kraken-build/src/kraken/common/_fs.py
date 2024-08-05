import contextlib
import errno
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO, AnyStr, BinaryIO, ContextManager, Literal, TextIO, overload


@overload
def atomic_file_swap(
    path: "str | Path",
    mode: Literal["w"],
    always_revert: bool = ...,
    create_dirs: bool = ...,
) -> ContextManager[TextIO]: ...


@overload
def atomic_file_swap(
    path: "str | Path",
    mode: Literal["wb"],
    always_revert: bool = ...,
    create_dirs: bool = ...,
) -> ContextManager[BinaryIO]: ...


@contextlib.contextmanager  # type: ignore[arg-type, misc]
def atomic_file_swap(
    path: "str | Path",
    mode: Literal["w", "wb"],
    always_revert: bool = False,
    create_dirs: bool = False,
) -> Iterator[IO[AnyStr]]:
    """
    Performs an atomic write to a file while temporarily moving the original file to a different random location.

    :param path: The path to replace.
    :param mode: The open mode for the file (text or binary).
    :param always_revert: If enabled, swap the old file back into place even if the with context has no errors.
    :param create_dirs: If the file does not exist, and neither do its parent directories, create the directories.
            The directory will be removed if the operation is reverted.
    """

    path = Path(path)

    with contextlib.ExitStack() as exit_stack:
        if path.is_file():
            old = exit_stack.enter_context(
                tempfile.NamedTemporaryFile(
                    mode,
                    prefix=path.stem + "~",
                    suffix="~" + path.suffix,
                    dir=path.parent,
                )
            )
            old.close()
            os.rename(path, old.name)
        else:
            old = None

        def _revert() -> None:
            assert isinstance(path, Path)
            if path.is_file():
                path.unlink()
            if old is not None:
                os.rename(old.name, path)

        if not path.parent.is_dir() and create_dirs:
            path.parent.mkdir(exist_ok=True)
            _old_revert = _revert

            def _revert() -> None:
                assert isinstance(path, Path)
                try:
                    shutil.rmtree(path.parent)
                finally:
                    _old_revert()

        try:
            with path.open(mode) as new:
                yield new
        except BaseException:
            _revert()
            raise
        else:
            if always_revert:
                _revert()
            else:
                if old is not None:
                    os.remove(old.name)


def safe_rmpath(path: Path) -> None:
    """
    Removes the specified *path* from the file system. If it is a directory, :func:`shutil.rmtree` will be used
    with `ignore_errors` enabled.
    """

    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise
