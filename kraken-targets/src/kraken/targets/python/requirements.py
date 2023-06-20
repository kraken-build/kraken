from dataclasses import dataclass

from kraken.targets.target import make_target_factory


@dataclass
class PythonRequirements:
    requirements: tuple[str]


python_requirements = make_target_factory("python_requirements", None, PythonRequirements)
