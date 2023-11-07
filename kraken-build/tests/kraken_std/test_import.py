from __future__ import annotations

import importlib
from collections.abc import Iterable, Iterator
from pathlib import Path


def iter_modules_recursively(prefix: str, path: Iterable[str | Path]) -> Iterator[str]:
    for p in map(Path, path):
        # Need at least one Python file in the directory to continue searching subdirectories.
        has_py_file = False
        subdirs = []
        for item in p.iterdir():
            if item.name == "__init__.py":
                yield prefix.rstrip(".")
            elif item.name.endswith(".py"):
                has_py_file = True
                yield prefix + item.name[:-3]
            elif item.is_dir():
                subdirs.append(item)

        if has_py_file:
            for item in subdirs:
                yield from iter_modules_recursively(prefix + item.name + ".", [item])


def test_import() -> None:
    package = importlib.import_module("kraken.std")
    for mod in sorted(iter_modules_recursively(package.__name__ + ".", package.__path__)):
        importlib.import_module(mod)
