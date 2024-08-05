from __future__ import annotations

import contextlib
import logging
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from kraken.core.system.context import Context
from kraken.core.system.project import Project

__all__ = [
    "kraken_ctx",
    "kraken_project",
]

logger = logging.getLogger(__name__)


@pytest.fixture(name="kraken_ctx")
def _kraken_ctx_fixture() -> Iterator[Context]:
    with kraken_ctx() as ctx:
        yield ctx


@contextlib.contextmanager
def kraken_ctx() -> Iterator[Context]:
    with tempfile.TemporaryDirectory() as tmpdir:
        context = Context(Path(tmpdir))
        with context.as_current():
            yield context


@pytest.fixture(name="kraken_project")
def _kraken_project_fixture(kraken_ctx: Context) -> Iterator[Project]:
    with kraken_project(kraken_ctx) as project:
        yield project


@contextlib.contextmanager
def kraken_project(kraken_ctx: Context) -> Iterator[Project]:
    with tempfile.TemporaryDirectory() as tmpdir:
        kraken_ctx.root_project = Project("test", Path(tmpdir), None, kraken_ctx)
        with kraken_ctx.root_project.as_current():
            yield kraken_ctx.root_project
