import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from pytest import fixture


@fixture
def tempdir() -> Iterator[Path]:
    with TemporaryDirectory() as tempdir:
        yield Path(tempdir)


@contextmanager
def chdir_context(path: Path) -> Iterator[None]:
    cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)
