import contextlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from kraken.std.python.tasks.pex_build_task import pex_set_global_store_path
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


# Speed up building PEX's in test.
pex_set_global_store_path(Path(__file__).parent.parent.parent / "build/.store")
