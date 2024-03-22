""" This module provides facilities for Kraken-infused Python projects.

__Features__

* Consume from and publish packages to alternative Python package indexes.
* Standardized Python project configuration (`src/` directory, `tests/` directory, tests with Pytest incl. doctests,
    Mypy, Black, isort, Pycln, Pyupgrade, Flake8).
* Supports [Slap][], [Poetry][] and [PDM][]-managed Python projects.
* Built-in Protobuf support (dependency management using [Buffrs][], linting with [Buf][] and code generation with
    [grpcio-tools][]).
* Produce a PEX application from your Python project using [`python_app()`](kraken.build.python.v1alpha1.python_app).

!!! note "Tools"
    Note that except for Pytest (which needs to be a development dependency to your Python project), all tools are
    installed for you automatically by Kraken.

[Slap]: https://github.com/NiklasRosenstein/slap
[Poetry]: https://python-poetry.org/docs
[PDM]: https://pdm-project.org/latest/
[Buffrs]: https://github.com/helsing-ai/buffrs
[Buf]: https://buf.build/
[grpcio-tools]: https://pypi.org/project/grpcio-tools/

!!! warning "Unstable API"
    This API is unstable and should be used with caution.
"""

from .project import python_app, python_package_index, python_project

__all__ = ["python_package_index", "python_project", "python_app"]
