from dataclasses import dataclass

from kraken.targets.core.target import make_target_factory


@dataclass(frozen=True)
class PythonSources:
    """
    Represents a set of Python source files.
    """

    sources: tuple[str]

    #: A constraint for the version of the Python interpreter that the sources are compatible with.
    interpreter_constraint: str | None = None


python_sources = make_target_factory("python_sources", None, PythonSources)
