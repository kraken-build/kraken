import contextlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.kraken_std.util.docker import DockerServiceManager


@pytest.fixture(scope="session")
def docker_service_manager() -> Iterator[DockerServiceManager]:
    with contextlib.ExitStack() as stack:
        yield DockerServiceManager(stack)


@pytest.fixture
def tempdir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as tempdir:
        yield Path(tempdir)


@contextlib.contextmanager
def chdir_context(path: Path) -> Iterator[None]:
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)
