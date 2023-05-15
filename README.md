<img align="center" src="docs/content/img/title.png">

&nbsp;

# kraken-build

Kraken is a task orchestration system. It sets itself apart from traditional build systems in that it does not
try to replace good build tooling that already exists, but instead build on top of it and orchestrate the
invokations of high-level tools like Cargo (Rust) and Poetry (Python).

The primary goal of Kraken is to drastically accelerate the setup of new projects and benefit from the ability
to roll out new features in the software development lifecycle at scale.

Kraken is currently primarily used and developed at [Helsing](https://helsing.ai).

## Getting started

Kraken is best invoked in your project using the Kraken wrapper CLI `krakenw`. It takes care of installing the same
version of Kraken for your project in any environment. The recommended way to install the wrapper is with Pipx.
You need to use Python 3.7 - 3.10 (3.11+ is currently not supported due to an upstream issue in Dill).

    $ pipx install kraken-wrapper

Kraken's build scripts are called `.kraken.py` and are written in Python. For `krakenw` to know what to install for
your project, you need to begin your script with a call to the `buildscript()` function. The `kraken-std` package
provides the core buisiness logic.

```py
from kraken.common import buildscript
buildscript(requirements=["kraken-std"])
```

Subsequently, you can import from the `kraken.std` module to import the functionality you need to describe your
project's build:

```py
from kraken.std import python
python.mypy()
python.flake8()
```

## Development

  [Slap]: https://github.com/NiklasRosenstein/slap

Kraken uses [Slap][] as the Python build backend. Currently, the repository is not configured to fully be fully
managed by Kraken itself (only `kraken-std` is). If you need a fresh installation of all Kraken components, you can
run the Slap CLI:

    $ slap venv -ac
    $ slap install --link

> You need at least Slap 1.9.0.

In CI, we currently use a combination of `krakenw` and Slap to test the repository. The `krakenw` CLI is used only
for `kraken-std` at the moment as it is the only one with a build script. However, we _always_ lag behind in the
version of Kraken we can use to self-manage the repository (i.e. the latest feature that you added to `kraken-std`
cannot be used in the same version of it to build itself).

## Releases

All packages in this repository are released under the same version number simultaneously. Regardless, we still
follow to indicate the severity of changes, and packages in this repository are expected to be compatible with
one another according to semantic versioning.

A release must be created by a maintainer that has write access to the `develop` branch. The release process
is automated usnig Slap.

    $ slap release -tp <patch|minor|major|x.y.z>
    $ slap publish
