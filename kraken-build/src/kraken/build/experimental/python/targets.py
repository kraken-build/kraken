from dataclasses import dataclass
from pathlib import Path
from kraken.core import Project, Target


@dataclass(frozen=True, kw_only=True)
class PythonSources(Target):
    """Represents a list of Python source files."""

    project: Project
    files: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class PythonRequirements(Target):
    """Represents a list of Python requirements."""

    requirements: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class PythonApp(Target):
    """Represents a Python app target, implying a bunch of other shit."""

    project: Project
    name: str
    entry_point: str

    # Interpreter constraint.
    interpreter_constraint: str | None = None

    # For inferring source files.
    source_directory: str = "src"
    tests_directory: str = "tests"

    # For infering requirements.
    requirements_file: str | None = None
    lock_file: str | None = None
    pyproject_toml: str | None = None


@dataclass(frozen=True, kw_only=True)
class PythonPex(Target):
    project: Project
    dependencies: tuple[str, ...]
    name: str
    entry_point: str
    interpreter_constraint: str | None


# Requests


@dataclass(frozen=True, kw_only=True)
class PythonRuntimeRequest:
    interpreter_constraint: str | None
    consider_pyenv: bool = True


@dataclass(frozen=True, kw_only=True)
class PythonRuntime:
    path: str
    version: str


@dataclass(frozen=True, kw_only=True)
class PexRequest(Target):
    """Represents a PEX binary to be built."""

    project: Project
    requirements: tuple[str, ...]
    entry_point: str
    binary_out: Path
    interpreter_constraint: str | None


@dataclass(frozen=True, kw_only=True)
class PexResult(Target):
    """Represents the output of a PEX binary."""

    binary_out: Path


@dataclass(frozen=True, kw_only=True)
class VenvRequest(Target):
    """Represents a Python virtual environment to install."""

    project: Project
    requirements: tuple[str, ...]
    interpreter_constraint: str | None = None
    upgrade_deps: bool = True
    system_site_packages: bool = False


@dataclass(frozen=True, kw_only=True)
class VenvResult(Target):
    python_bin: Path
