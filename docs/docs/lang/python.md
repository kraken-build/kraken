# Python

  [Kaniko]: https://github.com/GoogleContainerTools/kaniko
  [Buildx]: https://docs.docker.com/buildx/working-with-buildx/

Lint, format and test Python code.

__Supported tools__

* Black
* Flake8
* isort
* Mypy
* Pycln
* Pylint
* Pytest
* Pyupgrade

__Supported build systems (for installing/building)__

* Poetry
* Slap

## Build systems

A build system that is supported by Kraken is needed to use the {@pylink kraken.std.python.tasks.build_task.BuildTask}.
Most build systems will support managed Python environments for the current Python project (e.g. `poetry install` will
create a virtual environment and install the project into it).

Build systems implemented for Kraken will take care of the installation, ensuring that the Python package indexes
registered in the build script are made available to the installation process.

### Poetry

* **Package index credentials**: The installation process injects package index configurations into `poetry.toml` and
`pyproject.toml`
  * [TODO] Should we permanently inject the config into `pyproject.toml` and keep it in sync with a task?

### Slap

* **Package index credentials**: [TODO] The installation processs passes the extra index URLs to `slap install` using the
`--package-index` option.
  * [TODO] Should we add an option to permanently add a package index to the Slap configuration and then keep it in
    sync with a task?

## Publishing

Independent of the Python build system used, Kraken will use [Twine][] to publish to a Package index.

[Twine]: https://twine.readthedocs.io/en/stable/
