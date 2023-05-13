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

## API Documentation

@pydoc kraken.std.python.settings.python_settings

@pydoc kraken.std.python.settings.PythonSettings

### Info

@pydoc kraken.std.python.tasks.InfoTask

@pydoc kraken.sts.python.tasks.info

### Black

@pydoc kraken.std.python.tasks.black.BlackTask

@pydoc kraken.std.python.tasks.black.black

### Flake8

@pydoc kraken.std.python.tasks.flake8.Flake8Task

@pydoc kraken.std.python.tasks.flake8.flake8

### isort

@pydoc kraken.std.python.tasks.isort.IsortTask

@pydoc kraken.std.python.tasks.isort.isort

### Mypy

@pydoc kraken.std.python.tasks.mypy.MypyTask

@pydoc kraken.std.python.tasks.mypy.mypy

#### Stubtest

@pydoc kraken.std.python.tasks.mypy_stubtest.MypyStubtestTask

@pydoc kraken.std.python.tasks.mypy_stubtest.mypy_stubtest

### Pycln

@pydoc kraken.std.python.tasks.pycln.PyclnTask

@pydoc kraken.std.python.tasks.pycln.pycln

### Pylint

@pydoc kraken.std.python.tasks.pylint.PylintTask

@pydoc kraken.std.python.tasks.pylint.pylint

### Pytest

@pydoc kraken.std.python.tasks.pytest.PytestTask

@pydoc kraken.std.python.tasks.pytest.pytest

### Pyupgrade

@pydoc kraken.std.python.tasks.pyupgrade.PyUpgradeTask

@pydoc kraken.std.python.tasks.pyupgrade.PyUpgradeCheckTask

@pydoc kraken.std.python.tasks.pyupgrade.pyupgrade

__Environment variables__

* `PYTEST_FLAGS`
