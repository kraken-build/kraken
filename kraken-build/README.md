# The Kraken build system

![kraken-logo](https://i.imgur.com/Lqjy2zi.png)

[![Python](https://github.com/kraken-build/kraken/actions/workflows/python.yaml/badge.svg)](https://github.com/kraken-build/kraken/actions/workflows/python.yaml)
[![PyPI version](https://badge.fury.io/py/kraken-build.svg)](https://badge.fury.io/py/kraken-build)
[![Documentation](https://img.shields.io/badge/Documentation-blue?style=flat&logo=gitbook&logoColor=white)](https://kraken-build.github.io/kraken/)

Kraken is a build system, but not in the traditional sense. It's focus is on the orchestration of high-level tasks,
such as organization of your repository configuration, code generation, invoking other build systems, etc. It is not a
replacement for tools like Poetry, Cargo or CMake.

**Requirements**

- CPython 3.10+

## Getting started

[Pipx]: https://pypa.github.io/pipx/

Currently, Kraken's OSS components are not very well documented and do not provide a convenient way to get started.
However, if you really want to try it, you can use the following steps:

1. Install `kraken-wrapper` (e.g. with [Uv]) to get access to the `krakenw` command-line tool.
2. Create a `.kraken.py` script in your project's root directory.

   ```py
   from kraken.common import buildscript
   buildscript(requirements=["kraken-build==0.45.2"])

   from kraken.std import python
   python.mypy()
   python.ruff()
   ```

3. Run `krakenw lock` to install `kraken-build` for your project in `build/.kraken/venv` and generate a `kraken.lock` file.
4. Run `krakenw run lint` to run the linters.

> Note that you can also use the `kraken` CLI (instead of `krakenw`), however this will disregard the `buildscript()`
> function, will not use the lock file and will use the version of Kraken that was installed globally.

## Development

[Uv]: https://docs.astral.sh/uv/
[Mise]: https://mise.jdx.dev/

This repository uses [Uv], but not currently a Uv-workspace because Kraken does not support that, yet. You may
want to use a released version of `krakenw` instead of the live version in `kraken-wrapper/` to interact with this
repository. You can use [Mise] to install all the tools you need.

    $ mise install
    $ eval "$(mise activate)"
    $ krakenw run fmt lint test

## Release process

A release must be created by a maintainer that has write access to the `develop` branch.

    $ ./scripts/bump.py X.Y.Z
    $ git commit -m 'release X.Y.Z'
    $ git tag X.Y.Z
    $ git push origin develop X.Y.Z

The packages are published to PyPI from CI.
