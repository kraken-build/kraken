from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import pytest

from kraken.core.system.context import Context
from kraken.core.system.project import Project

if TYPE_CHECKING:
    from _pytest.fixtures import FixtureRequest

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
    context = Context(Path("build"))
    with context.as_current():
        yield context


@pytest.fixture(name="kraken_project")
def _kraken_project_fixture(kraken_ctx: Context, request: FixtureRequest) -> Iterator[Project]:
    with kraken_project(kraken_ctx, request.path) as project:
        yield project


@contextlib.contextmanager
def kraken_project(kraken_ctx: Context, path: Path | None = None) -> Iterator[Project]:
    if path is None:
        path = Path(sys._getframe(1).f_code.co_filename)
    kraken_ctx.root_project = Project("test", path.parent, None, kraken_ctx)
    with kraken_ctx.root_project.as_current():
        yield kraken_ctx.root_project
