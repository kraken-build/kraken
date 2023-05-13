""" Inspect a Python environment for all installed packages. """

import argparse
import csv
import dataclasses
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Union

import pkg_resources


@dataclasses.dataclass
class Distribution:
    """Additional metadata for a distribution."""

    name: str
    location: str
    version: str
    license_name: Optional[str]
    platform: Optional[str]
    requires_python: Optional[str]
    requirements: List[str]
    extras: Set[str]

    @staticmethod
    def from_pkg_resources(dist: pkg_resources.Distribution) -> "Distribution":
        from email.parser import Parser

        data = Parser().parsestr(dist.get_metadata(dist.PKG_INFO))

        return Distribution(
            name=dist.project_name,
            location=dist.location,
            version=data["Version"],
            license_name=data.get("License"),
            platform=data.get("Platform"),
            requires_python=data.get("Requires-Python"),
            requirements=data.get_all("Requires-Dist") or [],
            extras=set(data.get_all("Provides-Extra") or []),
        )

    @staticmethod
    def from_json(data: Dict[str, Any]) -> "Distribution":
        dist = Distribution(**data)
        dist.extras = set(data["extras"])
        return dist

    def to_json(self) -> Dict[str, Any]:
        result = {field.name: getattr(self, field.name) for field in dataclasses.fields(self)}
        result["extras"] = list(self.extras)
        return result

    def to_csv_row(self) -> List[Optional[str]]:
        requirements = "|".join(self.requirements)
        extras = ",".join(self.extras)
        return [
            self.name,
            self.location,
            self.version,
            self.license_name,
            self.platform,
            self.requires_python,
            requirements,
            extras,
        ]


class DistributionCollector:
    distributions: Dict[str, Distribution]

    def __init__(self) -> None:
        self.distributions = {}

    def collect(self, requirement: Union[str, pkg_resources.Requirement], recursive: bool = True) -> Distribution:
        """Collect the distribution named *dist_name*.

        :param requirement: The distribution name or requirement to collect.
        :param recursive: Whether to recursively collect the dependencies of the distribution.
        """

        if isinstance(requirement, str):
            requirement = next(pkg_resources.parse_requirements(requirement))

        if requirement.project_name in self.distributions:
            return self.distributions[requirement.project_name]

        dist = Distribution.from_pkg_resources(pkg_resources.get_distribution(requirement))
        self.distributions[dist.name] = dist

        if recursive:
            for dep in dist.requirements:
                self.collect(dep, recursive=True)

        return dist

    def collect_multiple(self, requirements: Iterable[Union[str, pkg_resources.Requirement]]) -> None:
        for requirement in requirements:
            self.collect(requirement)

    def collect_all(self, sys_path: Optional[Iterable[str]] = None) -> None:
        for path in sys_path or sys.path:
            for dist in pkg_resources.find_distributions(path):
                self.distributions[dist.project_name] = Distribution.from_pkg_resources(dist)


def get_distributions() -> Dict[str, Distribution]:
    """Returns all distributions that can be found in the current Python environment."""

    collector = DistributionCollector()
    collector.collect_all()
    return collector.distributions


def get_distributions_of(python_bin: Union[str, Path]) -> Dict[str, Distribution]:
    """Returns all distributions that can be found in the environment of the given Python executable. The Python
    version must have the `setuptools` package installed and be able to execute the code of this library, i.e. it
    must be at least Python 3.6 or higher."""

    command = [str(python_bin), __file__, "--json"]
    dists = [Distribution.from_json(json.loads(x)) for x in subprocess.check_output(command).decode().splitlines()]
    return {dist.name: dist for dist in dists}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="output in JSON format (default)")
    parser.add_argument("--csv", action="store_true", help="output in CSV format")
    parser.add_argument("--python", help="read the distributions of the environment of the given Python executable")
    args = parser.parse_args()

    if args.python:
        dists = get_distributions_of(args.python)
    else:
        dists = get_distributions()

    if args.csv:
        header = [field.name for field in dataclasses.fields(Distribution)]
        writer = csv.writer(sys.stdout)
        writer.writerow(header)
        for dist in dists.values():
            row = dist.to_csv_row()
            writer.writerow(row)
    else:
        for dist in dists.values():
            json.dump(dist.to_json(), sys.stdout)
            sys.stdout.write("\n")


if __name__ == "__main__":
    main()
