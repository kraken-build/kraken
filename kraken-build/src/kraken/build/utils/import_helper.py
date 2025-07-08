import sys
import types
from typing import Any

from kraken.core import Context, Project


class _KrakenBuildModuleWrapper:
    """A wrapper for the `kraken.build` module to allow build-scripts to always import the current (i.e. their own)
    project and the Kraken build context."""

    def __init__(self, module: types.ModuleType) -> None:
        self.__module = module

    def __getattr__(self, name: str) -> Any:
        if name == "context":
            return Context.current()
        elif name == "project":
            return Project.current()
        else:
            return getattr(self.__module, name)

    @staticmethod
    def install(module_name: str) -> None:
        """Install the wrapper around the given module."""
        sys.modules[module_name] = _KrakenBuildModuleWrapper(sys.modules[module_name])  # type: ignore[assignment]
