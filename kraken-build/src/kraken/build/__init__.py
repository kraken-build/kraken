from kraken.core import Context, Project
from .utils.import_helper import _KrakenBuildModuleWrapper

# Install a wrapper around the module object to allow build-scripts to always import the current (i.e. their own)
# project and the Kraken build context.
context: Context
""" When importing this object, you always get the current `kraken.core.Context` that you would also receive by
calling `kraken.core.Context.current()` at the same instant in your code. This is a convenience helper for build
scripts that need access to the build context. """

project: Project
""" When importing this object, you always get the current `kraken.core.Project` that you would also receive by
calling `kraken.core.Project.current()` at the same instant in your code. This is a convenience helper for build
scripts that needs access to their project. """

_KrakenBuildModuleWrapper.install(__name__)

__all__ = ["context", "project"]
