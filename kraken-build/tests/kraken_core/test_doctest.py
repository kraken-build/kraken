from __future__ import annotations

import doctest
import re
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path

import pytest

import kraken.core

# NOTE(NiklasRosenstein): We do the doctest manually instead of relying on `pytest --doctest-modules` because
#       it does not handle PEP420 implicit namespace packages very well.
#
#       See also: https://github.com/pytest-dev/pytest/issues/1927


def iter_modules_recursive(prefix: str, path: Path) -> Iterator[tuple[str, Path]]:
    for item in path.iterdir():
        item_name = prefix + item.stem
        if item.is_dir() and re.match(r"[a-zA-Z\_][a-zA-Z0-9\_]*", item.name):
            yield from iter_modules_recursive(item_name + ".", item)
        elif item.suffix == ".py":
            yield (item_name.rstrip("."), item)


excluded_modules = [
    # NOTE(NiklasRosenstein): These modules are present only for backwards compatibility and will only
    #       trigger a warning and have no doctests.
    "kraken.core.context",
    "kraken.core.executor",
    "kraken.core.graph",
    "kraken.core.project",
    "kraken.core.property",
    "kraken.core.supplier",
    "kraken.core.task",
    "kraken.core.test",
]


@pytest.mark.parametrize(
    argnames=("module",),
    argvalues=[
        (name,)
        for name, _path in iter_modules_recursive("kraken.core.", Path(kraken.core.__file__).parent)
        if name not in excluded_modules
    ],
)
def test__doctest(module: str) -> None:
    mod = import_module(module)
    failed, _succeeded = doctest.testmod(mod)
    assert failed == 0
