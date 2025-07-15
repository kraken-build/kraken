import contextlib
import errno
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from posixpath import normpath
from typing import IO, AnyStr, BinaryIO, ContextManager, Literal, Sequence, TextIO, overload


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


def intersect_paths(
    left: Sequence[Path],
    right: Sequence[Path],
    left_relative_to: Path | None = None,
    right_relative_to: Path | None = None,
) -> list[Path]:
    """
    Calculates the hierarchical intersection of two sequences of paths.

    This function compares each path in `left` against each path in `right` to find hierarchical overlaps. An overlap
    occurs if one path is a sub-path of the other (e.g., `/home/user` and `/home/user/docs`).

    When an overlap is found between a pair of paths, the more specific (deeper) path of the two is added to the result.

    The format of each returned path (absolute or relative) depends on the format of the *left* path from the
    original input. For example, if a path `A` from `left` contains path `B` from `right`:

    - The result will include path `B`.
    - Path `B` will be relative to `left_relative_to` if `A` was originally a relative path.
    - Otherwise, path `B` will be absolute.

    If in the reverse case, path `B` from `right` contains path `A` from `left`:

    - The result will include path `A`.
    - Path `A` will be relative to the `left_relative_to` if `A` was originally a relative path.
    - Otherwise, path `A` will be absolute.

    Args:
        left: A sequence of paths to compare against `right`.
        right: A sequence of paths to compare against `left`.
        left_relative_to: The base directory to resolve relative paths in `left`. Defaults to the current working
            directory if `None`.
        right_relative_to: The base directory to resolve relative paths in `right`. Defaults to the current working
            directory if `None`.

    Returns:
        A sequence of `Path` objects representing the more specific paths from each hierarchical overlap found.

    Examples:

        >>> from pathlib import PosixPath
        >>> intersect_paths(
        ...     left=[PosixPath("/home/user")],
        ...     right=[PosixPath("/home/user/Documents/PDFs"), PosixPath("artifacts"), PosixPath("/var/lib")],
        ...     right_relative_to=PosixPath("/home/user/Downloads"),
        ... )
        [PosixPath('/home/user/Documents/PDFs'), PosixPath('/home/user/Downloads/artifacts')]

        # Same as the previous, but with left and right flipped.
        >>> intersect_paths(
        ...     left=[PosixPath("/home/user/Documents/PDFs"), PosixPath("artifacts"), PosixPath("/var/lib")],
        ...     right=[PosixPath("/home/user")],
        ...     left_relative_to=PosixPath("/home/user/Downloads"),
        ...     right_relative_to=PosixPath("/home/user"),
        ... )
        [PosixPath('/home/user/Documents/PDFs'), PosixPath('artifacts')]

        >>> intersect_paths(
        ...     left=[PosixPath("src")],
        ...     right=[PosixPath("src/utils.py"), PosixPath("/project/src/tests")],
        ...     left_relative_to=PosixPath("/project"),
        ...     right_relative_to=PosixPath("/project"),
        ... )
        [PosixPath('src/utils.py'), PosixPath('src/tests')]

        >>> intersect_paths(
        ...     left=[PosixPath("/absolute/path")],
        ...     right=[PosixPath("relative/path"), PosixPath("/absolute/path/file.txt")],
        ...     left_relative_to=None,
        ...     right_relative_to=PosixPath("/absolute"),
        ... )
        [PosixPath('/absolute/path/file.txt')]

        >>> intersect_paths(
        ...     left=[PosixPath("/path1")],
        ...     right=[PosixPath("/path2")],
        ... )
        []

        >>> intersect_paths(
        ...     left=[PosixPath("/project/src"), PosixPath("tests/core")],
        ...     right=[PosixPath(".")],
        ...     left_relative_to=PosixPath("/project"),
        ...     right_relative_to=PosixPath("/project"),
        ... )
        [PosixPath('/project/src'), PosixPath('tests/core')]

        >>> intersect_paths(
        ...     left=[PosixPath("/project/src"), PosixPath("/project/src/tests/foo/..")],
        ...     right=[PosixPath(".")],
        ...     left_relative_to=PosixPath("/project"),
        ...     right_relative_to=PosixPath("/project"),
        ... )
        [PosixPath('/project/src'), PosixPath('/project/src/tests')]
    """

    cwd = Path.cwd()
    if left_relative_to is None:
        left_relative_to = cwd
    if right_relative_to is None:
        right_relative_to = cwd

    left_absolute = [p.is_absolute() for p in left]
    right_absolute = [p.is_absolute() for p in right]
    left_paths = [Path(normpath((left_relative_to.joinpath(p) if left_relative_to else p).absolute())) for p in left]
    right_paths = [
        Path(normpath((right_relative_to.joinpath(p) if right_relative_to else p).absolute())) for p in right
    ]
    result = []

    for left_abs, left_path in zip(left_absolute, left_paths):
        for right_abs, right_path in zip(right_absolute, right_paths):
            if right_path.is_relative_to(left_path):
                if not left_abs:
                    right_path = right_path.relative_to(left_relative_to)
                result.append(right_path)
            elif left_path.is_relative_to(right_path):
                if not left_abs:
                    left_path = left_path.relative_to(left_relative_to)
                result.append(left_path)

    return result
