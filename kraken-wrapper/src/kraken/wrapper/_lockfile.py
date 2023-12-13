from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any

from kraken.common import LocalRequirement, PipRequirement, RequirementSpec
from packaging.requirements import Requirement as ParsedRequirement


@dataclasses.dataclass(frozen=True)
class Distribution:
    name: str
    version: str
    requirements: list[str]
    extras: set[str]


@dataclasses.dataclass
class Lockfile:
    requirements: RequirementSpec
    pinned: dict[str, str]

    @staticmethod
    def from_path(path: Path) -> Lockfile:
        import tomli

        with path.open("rb") as fp:
            return Lockfile.from_json(tomli.load(fp))

    def write_to(self, path: Path) -> None:
        import tomli_w

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fp:
            tomli_w.dump(self.to_json(), fp)

    @staticmethod
    def from_json(data: dict[str, Any]) -> Lockfile:
        return Lockfile(
            requirements=RequirementSpec.from_json(data["requirements"]),
            pinned=data["pinned"],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "requirements": self.requirements.to_json(),
            "pinned": self.pinned,
        }

    def to_pinned_requirement_spec(self) -> RequirementSpec:
        """Converts the pinned versions in the lock file to a :class:`RequirementSpec` with the pinned requirements."""

        requirements = RequirementSpec(
            requirements=(),
            index_url=self.requirements.index_url,
            extra_index_urls=self.requirements.extra_index_urls[:],
            pythonpath=self.requirements.pythonpath[:],
            interpreter_constraint=self.requirements.interpreter_constraint,
        )

        # Make sure that local requirements keep being installed from the local source.
        local_requirements = {
            dep.name: dep for dep in self.requirements.requirements if isinstance(dep, LocalRequirement)
        }
        requirements = requirements.with_requirements(local_requirements.values())

        # Add all non-local requirements with exact version numbers.
        requirements = requirements.with_requirements(
            f"{key}=={value}" for key, value in sorted(self.pinned.items()) if key not in local_requirements
        )

        return requirements


def normalize_package_name(name: str) -> str:
    # PEP503/PEP426 normalized package name.
    return re.sub(r"[-_.]+", "-", name).lower()


def calculate_lockfile(
    requirements: RequirementSpec,
    distributions: list[Distribution],
) -> tuple[Lockfile, set[str]]:
    """Calculate the lockfile of the environment.

    :param requirements: The requirements that were used to install the environment. These requirements
        will be embedded as part of the returned lockfile.
    :return: (lockfile, extra_distributions)
    """

    # Contains the versions we pinned.
    pinned: dict[str, str] = {}

    # Normalize distribution names.
    dists = {normalize_package_name(dist.name): dist for dist in distributions}

    # Convert our internal requirements representation to parsed requirements. Local requirements
    # are treated without extras.
    requirements_stack = [
        ParsedRequirement(str(req) if isinstance(req, PipRequirement) else req.name)
        for req in requirements.requirements
    ]

    while requirements_stack:
        package_req = requirements_stack.pop(0)
        package_name = normalize_package_name(package_req.name)

        if package_name in pinned:
            # Already collected it.
            # TODO (@NiklasRosenstein): Maybe this req has extras we haven't considered yer?
            # NOTE (@NiklasRosenstein): We may be missing the package because it's a requirement that is only
            #       installed under certain conditions (e.g. markers/extras).
            continue

        # Pin the package version.
        dist = dists[package_name]
        pinned[package_name] = dist.version

        # Filter the requirements of the distribution down to the ones required according to markers and the
        # current package requirement's extras.
        for req in map(ParsedRequirement, dist.requirements):
            if not req.marker or any(req.marker.evaluate({"extra": extra}) for extra in package_req.extras):
                requirements_stack.append(req)

    extra_distributions = dists.keys() - pinned.keys()
    pinned = {k: v for k, v in sorted(pinned.items(), key=lambda t: t[0].lower())}
    return Lockfile(requirements, pinned), extra_distributions
