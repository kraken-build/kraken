from collections.abc import Sequence
from typing import Any
from kraken.build.python.targets import PythonApp, PythonPex, PythonRequirements, PythonSources

from kraken.core.system.target import NamedTarget


def python_sources(
    name: str,
    sources: list[str],
) -> NamedTarget[PythonSources]:
    """Define a target that represents a static list of Python source files."""

    from kraken.build import project

    return project.define_target(name, PythonSources(project=project, files=tuple(sources)))


def python_requirements(
    name: str,
    requirements: Sequence[str],
) -> NamedTarget[PythonRequirements]:
    """Define a target that represents a static list of Python requirements."""

    from kraken.build import project

    return project.define_target(name, PythonRequirements(requirements=tuple(requirements)))


def python_library(
    name: str,
    source_directory: str = "src",
    tests_directory: str = "tests",
    package_name: str | None = None,
    packages: list[str] | None = None,
    modules: list[str] | None = None,
) -> None:
    """Define a target the represents an installable Python library. The target will be installed into a virtual
    environment for local development and testing.

    :param name: The name of the target.
    :param source_directory: The directory containing the source files for the library.
    :param package_name: The name of the package. If not specified, the name will be read from the project's
        `pyproject.toml`. If the `pyproject.toml` does not exist, the name will be inferred from the target name.
    :param packages: A list of packages to include in the library. If not specified, the packages will be read from
        the project's `pyproject.toml`. If the `pyproject.toml` does not exist, the packages will be inferred from
        the target name.
    :param modules: A list of modules to include in the library. If not specified, the modules will be read from
        the project's `pyproject.toml`. If the `pyproject.toml` does not exist, the modules will be inferred from
        the target name.

    This target is a shorthand for manually defining `python_sources()`, `python_requirements()`, `python_venv()` and
    `python_package()` targets.
    """


def python_app(name: str, **kwargs: Any) -> None:
    """Define a target that builds a Python application. Similar to a #python_library(), a #python_app() target
    defines a Python project that will be installed into a virtual environment for local development and testing,
    but will additionally produce a PEX application.

    :param name: The name of the target.

    This target is a shorthand for manually defining `python_sources()`, `python_requirements()`, `python_venv()` and
    `python_pex_binary()`.
    """

    # TODO: Support interpreter_constraint (configurable or inferred).
    # TODO: Invoke Python testing, linting and formatting tools.

    from kraken.build import project

    project.define_target(name, PythonApp(project=project, name=name, **kwargs))
    project.define_target(
        f"{name}.pex",
        PythonPex(
            project=project,
            dependencies=(name,),
            interpreter_constraint=kwargs.get("interpreter_constraint"),
            name=name,
            entry_point=kwargs["entry_point"],
        ),
    )

    # TODO: Define a separate target for the PEX so we can separate running the app from the built
    #       PEX or the virtual environment.
