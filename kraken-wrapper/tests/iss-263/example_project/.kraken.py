from kraken.common import buildscript

buildscript(requirements=["kraken-build == 0.37.3", "dependency @ ../dependency"])

from kraken.build import project

project.subproject("subproject")
