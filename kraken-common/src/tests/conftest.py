import contextlib
import os
import tempfile
import typing
from pathlib import Path

import pytest


@pytest.fixture
def tempdir() -> typing.Iterator[Path]:
    with tempfile.TemporaryDirectory() as tempdir:
        yield Path(tempdir)


@contextlib.contextmanager
def chdir_context(path: Path) -> typing.Iterator[None]:
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)
