# The Kraken build system

![kraken-logo](https://i.imgur.com/Lqjy2zi.png)

[![Python](https://github.com/kraken-build/kraken/actions/workflows/python.yaml/badge.svg)](https://github.com/kraken-build/kraken/actions/workflows/python.yaml)
[![PyPI version](https://badge.fury.io/py/kraken-build.svg)](https://badge.fury.io/py/kraken-build)
[![Documentation](https://img.shields.io/badge/Documentation-blue?style=flat&logo=gitbook&logoColor=white)](https://kraken-build.github.io/kraken/)

Kraken is a build system, but not in the traditional sense. It's focus is on the orchestration of high-level tasks,
such as organization of your repository configuration, code generation, invoking other build systems, etc. It is not a
replacement for tools like Poetry, Cargo or CMake.

__Requirements__

* CPython 3.10+

## Getting started

  [Pipx]: https://pypa.github.io/pipx/

Currently, Kraken's OSS components are not very well documented and do not provide a convenient way to get started.
However, if you really want to try it, you can use the following steps:

1. Install `kraken-wrapper` (e.g. with [Pipx][]) to get access to the `krakenw` command-line tool.
2. Create a `.kraken.py` script in your project's root directory.

    ```py
    from kraken.common import buildscript
    buildscript(requirements=["kraken-build==0.32.3"])
    
    from kraken.std.python import mypy, black, isort
    mypy()
    black()
    isort()
    ```
3. Run `krakenw lock` to install `kraken-build` for your project in `build/.kraken/venv` and generate a `kraken.lock` file.
4. Run `krakenw run lint` to run the linters.

> Note that you can also use the `kraken` CLI (instead of `krakenw`), however this will disregard the `buildscript()`
> function, will not use the lock file and will use the version of Kraken that was installed globally.

## How-to's

### Upgrade a project's lock file

To upgrade a project's lock file, run `krakenw lock --upgrade`. This will upgrade all dependencies to the latest
available version. If you want to upgrade based on updated constraints in `.kraken.py` without installing from scratch,
add the `--incremental` flag or set `KRAKENW_INCREMENTAL=1`.

## Development

  [Slap]: https://github.com/NiklasRosenstein/slap

This repository uses [Slap][] to manage the Python project. After installing Slap with Pipx, run the following to
install Kraken for development.

```
$ slap venv -c --python python3.10
$ slap install --link
# If you have the Slap shell magic installed, it will activate the Venv in your shell.
$ slap venv -a
```

You may want to use a released version of `krakenw` to interact in the repository however:

    $ krakenw python.install
    $ krakenw run fmt lint test

### Releases

A release must be created by a maintainer that has write access to the `develop` branch. The release process
is automated using Slap.

    $ slap release -tp <patch|minor|major|x.y.z>
    $ slap publish
