# kraken-build

[![Python](https://github.com/kraken-build/kraken/actions/workflows/python.yaml/badge.svg)](https://github.com/kraken-build/kraken/actions/workflows/python.yaml) |
[![PyPI version](https://badge.fury.io/py/kraken-build.svg)](https://badge.fury.io/py/kraken-build) |
[Documentation](https://kraken-build.github.io/kraken/)

Kraken is (not) a build system. It's focus is on the orchestration of high-level tasks, such as organization of your
repository configuration, code generation, invoking other build systems, etc. It is not a replacement for tools like
Poetry, Cargo or CMake.

## Getting started

  [Pipx]: https://pypa.github.io/pipx/

Currently, Kraken's OSS components are not very well documented and do not provide a convenient way to get started.
However, if you really want to try it, you can use the following steps:

1. Install `kraken-build` (e.g. with [Pipx][]) to get access to the `krakenw` command-line tool.
2. Create a `.kraken.py` script in your project's root directory.

    ```py
    from kraken.common import buildscript
    buildscript(requirements=["kraken-build ^0.31.7"])
    
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
