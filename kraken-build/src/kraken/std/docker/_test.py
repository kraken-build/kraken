from importlib import import_module

import pytest

from kraken.std.docker import BUILD_BACKENDS


@pytest.mark.parametrize(argnames="backend", argvalues=BUILD_BACKENDS.keys())
def test_build_backends_importable(backend: str) -> None:
    module_name, member = BUILD_BACKENDS[backend].rpartition(".")[::2]
    module = import_module(module_name)
    print(module)
    assert hasattr(module, member)
