"""
This tests for [#263 &mdash; local dependency is not considered relative to the root `.kraken.py`][263].

[263]: https://github.com/kraken-build/kraken/issues/263
"""

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from kraken.wrapper.main import main

EXAMPLE_PROJECT = Path(__file__).parent / "example_project"
DEPENDENCY = Path(__file__).parent / "dependency"


@contextmanager
def chdir(path: Path) -> Iterator[None]:
    cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


def test__issue_263__local_dependency_is_considered_relative_to_project_root() -> None:
    with TemporaryDirectory() as tmp:
        shutil.copytree(DEPENDENCY, Path(tmp) / DEPENDENCY.name)
        shutil.copytree(EXAMPLE_PROJECT, Path(tmp) / EXAMPLE_PROJECT.name)

        with chdir(Path(tmp) / EXAMPLE_PROJECT.name / "subproject"):
            with pytest.raises(SystemExit) as excinfo:
                main(["--use", "UV", "run", "-s"])
            assert excinfo.value.code == 0

        # We expect that the example_project/subproject/.kraken.py creates a file.
        assert (Path(tmp) / EXAMPLE_PROJECT.name / "subproject" / "answer.txt").read_text() == "42"
