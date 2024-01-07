from kraken.core import Context, Project
from .utils.import_helper import _KrakenBuildModuleWrapper

# Install a wrapper around the module object to allow build-scripts to always import the current (i.e. their own)
# project and the Kraken build context.
context: Context
project: Project

_KrakenBuildModuleWrapper.install(__name__)

__all__ = ["context", "project"]
