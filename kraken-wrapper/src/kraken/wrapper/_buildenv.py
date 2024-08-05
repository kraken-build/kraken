from __future__ import annotations

import abc
import dataclasses
import datetime
import json
import logging
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from kraken.common import EnvironmentType, NotSet, RequirementSpec, datetime_to_iso8601, iso8601_to_datetime

from ._lockfile import Distribution

logger = logging.getLogger(__name__)

KRAKEN_MAIN_IMPORT_SNIPPET = """
try:
    from kraken.core.cli.main import main  # >= 0.9.0
except ImportError:
    from kraken.cli.main import main  # < 0.9.0
""".strip()


class BuildEnv(abc.ABC):
    """Interface for the build environment."""

    @abc.abstractmethod
    def get_type(self) -> EnvironmentType:
        """Return the type of build environment that this is."""

    @abc.abstractmethod
    def get_path(self) -> Path:
        """Return the path to the build environment."""

    @abc.abstractmethod
    def get_installed_distributions(self) -> list[Distribution]:
        """Return the distributions that are currently installed in the environment."""

    @abc.abstractmethod
    def build(self, requirements: RequirementSpec, transitive: bool) -> None:
        """Build the environment from the given requirement spec."""

    @abc.abstractmethod
    def dispatch_to_kraken_cli(self, argv: list[str]) -> NoReturn:
        """Dispatch the kraken cli command in *argv* to the build environment.

        :param argv: The arguments to pass to the kraken cli (without the "kraken" command name itself)."""


@dataclasses.dataclass(frozen=True)
class BuildEnvMetadata:
    created_at: datetime.datetime
    environment_type: EnvironmentType
    requirements_hash: str
    hash_algorithm: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BuildEnvMetadata:
        return cls(
            created_at=iso8601_to_datetime(data["created_at"]),
            environment_type=EnvironmentType[data["environment_type"]],
            requirements_hash=data["requirements_hash"],
            hash_algorithm=data["hash_algorithm"],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "created_at": datetime_to_iso8601(self.created_at),
            "environment_type": self.environment_type.name,
            "requirements_hash": self.requirements_hash,
            "hash_algorithm": self.hash_algorithm,
        }


@dataclasses.dataclass
class BuildEnvMetadataStore:
    path: Path

    def __post_init__(self) -> None:
        self._metadata: BuildEnvMetadata | None | NotSet = NotSet.Value

    def get(self) -> BuildEnvMetadata | None:
        if self._metadata is NotSet.Value:
            if self.path.is_file():
                self._metadata = BuildEnvMetadata.from_json(json.loads(self.path.read_text()))
            else:
                self._metadata = None
        return self._metadata

    def set(self, metadata: BuildEnvMetadata) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(metadata.to_json()))
        self._metadata = metadata


class BuildEnvError(Exception):
    """
    An error occurred while building the environment.
    """


def general_get_installed_distributions(kraken_command_prefix: Sequence[str]) -> list[Distribution]:
    command = [*kraken_command_prefix, "query", "env"]
    output = subprocess.check_output(command).decode()
    return [Distribution(x["name"], x["version"], x["requirements"], x["extras"]) for x in json.loads(output)]
