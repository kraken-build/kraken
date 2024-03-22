from kraken.common import buildscript

buildscript(requirements=["kraken-build>=0.33.2"])

from kraken.build import project

project.subproject("docs")
project.subproject("kraken-build")
project.subproject("kraken-wrapper")
