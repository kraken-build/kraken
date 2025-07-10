from kraken.common import buildscript

buildscript(requirements=["kraken-build>=0.44.0"])

from kraken.build import project  # noqa: E402
from kraken.std.git import gitignore  # noqa: E402

gitignore()
project.subproject("docs")
project.subproject("kraken-build")
project.subproject("kraken-wrapper")
