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

@pydoc kraken.std.python.tasks.info_task.InfoTask
@pydoc kraken.sts.python.tasks.info_task.info

### Black

@pydoc kraken.std.python.tasks.black_task.BlackTask
@pydoc kraken.std.python.tasks.black_task.black

### Flake8

@pydoc kraken.std.python.tasks.flake8_task.Flake8Task
@pydoc kraken.std.python.tasks.flake8_task.flake8

### isort

@pydoc kraken.std.python.tasks.isort_task.IsortTask
@pydoc kraken.std.python.tasks.isort_task.isort

### Mypy

@pydoc kraken.std.python.tasks.mypy_task.MypyTask
@pydoc kraken.std.python.tasks.mypy_task.mypy

#### Stubtest

@pydoc kraken.std.python.tasks.mypy_subtest_task.MypyStubtestTask
@pydoc kraken.std.python.tasks.mypy_subtest_task.mypy_stubtest

### Pycln

@pydoc kraken.std.python.tasks.pycln_task.PyclnTask
@pydoc kraken.std.python.tasks.pycln_task.pycln

### Pylint

@pydoc kraken.std.python.tasks.pylint_task.PylintTask
@pydoc kraken.std.python.tasks.pylint_task.pylint

### Pytest

@pydoc kraken.std.python.tasks.pytest_task.PytestTask
@pydoc kraken.std.python.tasks.pytest_task.pytest

__Environment variables__

* `PYTEST_FLAGS`

### Pyupgrade

@pydoc kraken.std.python.tasks.pyupgrade_task.PyUpgradeTask
@pydoc kraken.std.python.tasks.pyupgrade_task.PyUpgradeCheckTask
@pydoc kraken.std.python.tasks.pyupgrade_task.pyupgrade
