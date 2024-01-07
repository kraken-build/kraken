""" `kraken.build` contains the experimental V2 build system for Kraken. All content except for the `context`
and `project` variables should be considered experimental and unstable.
"""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from kraken.core import Context, Project
from .utils.import_helper import _KrakenBuildModuleWrapper

# Install a wrapper around the module object to allow build-scripts to always import the current (i.e. their own)
# project and the Kraken build context.
context: Context
project: Project

_KrakenBuildModuleWrapper.install(__name__)

__all__ = ["context", "project"]
