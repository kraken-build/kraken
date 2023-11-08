""" Inspect a Python environment for all installed packages. """

import argparse
import csv
import dataclasses
import json
import subprocess
import sys
from collections.abc import Iterable
from importlib.metadata import (
    Distribution as _Distribution,
    distribution as _distribution,
    distributions as _distributions,
)
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement


@dataclasses.dataclass
class Distribution:
    """Additional metadata for a distribution."""

    name: str
    version: str
    license_name: str | None
    platform: str | None
    requires_python: str | None
    requirements: list[str]
    extras: set[str]

    @staticmethod
    def of(dist_name: str) -> "Distribution":
        return Distribution.from_importlib(_distribution(dist_name))

    @staticmethod
    def from_importlib(dist: _Distribution) -> "Distribution":
        return Distribution(
            name=dist.name,
            version=dist.metadata["Version"],
            license_name=dist.metadata["License"],
            platform=dist.metadata["Platform"],
            requires_python=dist.metadata["Requires-Python"],
            requirements=dist.metadata.get_all("Requires-Dist") or [],
            extras=set(dist.metadata.get_all("Provides-Extra") or []),
        )

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Distribution":
        dist = Distribution(**data)
        dist.extras = set(data["extras"])
        return dist

    def to_json(self) -> dict[str, Any]:
        result = {field.name: getattr(self, field.name) for field in dataclasses.fields(self)}
        result["extras"] = list(self.extras)
        return result

    def to_csv_row(self) -> list[str | None]:
        requirements = "|".join(self.requirements)
        extras = ",".join(self.extras)
        return [
            self.name,
            self.version,
            self.license_name,
            self.platform,
            self.requires_python,
            requirements,
            extras,
        ]


class DistributionCollector:
    distributions: dict[str, Distribution]

    def __init__(self) -> None:
        self.distributions = {}

    def collect(self, requirement: str | Requirement, recursive: bool = True) -> Distribution:
        """Collect the distribution named *dist_name*.

        :param requirement: The distribution name or requirement to collect.
        :param recursive: Whether to recursively collect the dependencies of the distribution.
        """

        if isinstance(requirement, str):
            requirement = Requirement(requirement)

        if requirement.name in self.distributions:
            return self.distributions[requirement.name]

        dist = Distribution.of(requirement.name)
        self.distributions[dist.name] = dist

        if recursive:
            for dep in dist.requirements:
                self.collect(dep, recursive=True)

        return dist

    def collect_multiple(self, requirements: Iterable[str | Requirement]) -> None:
        for requirement in requirements:
            self.collect(requirement)

    def collect_all(self, sys_path: Iterable[str] | None = None) -> None:
        for dist in _distributions(path=list(sys.path if sys_path is None else sys_path)):
            self.distributions[dist.name] = Distribution.from_importlib(dist)


def get_distributions() -> dict[str, Distribution]:
    """Returns all distributions that can be found in the current Python environment."""

    collector = DistributionCollector()
    collector.collect_all()
    return collector.distributions


def get_distributions_of(python_bin: str | Path) -> dict[str, Distribution]:
    """Returns all distributions that can be found in the environment of the given Python executable."""

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
