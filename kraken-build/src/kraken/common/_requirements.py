import abc
import argparse
import dataclasses
import hashlib
import logging
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ._buildscript import BuildscriptMetadata
from ._generic import NotSet, flatten

logger = logging.getLogger(__name__)
DEFAULT_BUILD_SUPPORT_FOLDER = "build-support"
DEFAULT_INTERPRETER_CONSTRAINT = ">=3.10"


def parse_requirement(value: str) -> "PipRequirement | LocalRequirement | UrlRequirement":
    """
    Parse a string as a requirement. Return a :class:`PipRequirement` or :class:`LocalRequirement`.
    """

    if match := re.match(r"(.+?)@(.+)", value):
        name, value = match.group(1).strip(), match.group(2).strip()
        if match := re.match(r"(git\+)?(ssh|https?)://.+", value):
            return UrlRequirement(name, value)
        return LocalRequirement(name, Path(value))

    match = re.match(r"([\w\d\-\_]+)(.*)", value)
    if match:
        return PipRequirement(match.group(1), match.group(2).strip() or None)

    raise ValueError(f"invalid requirement: {value!r}")


class Requirement(abc.ABC):
    name: str  #: The distribution name.

    @abc.abstractmethod
    def to_args(self, base_dir: Path) -> list[str]:
        """Convert the requirement to Pip args."""

        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class PipRequirement(Requirement):
    """Represents a Pip requriement."""

    name: str
    spec: str | None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(f"invalid URL requirement: {self}")

    def __str__(self) -> str:
        return f"{self.name}{self.spec or ''}"

    def to_args(self, base_dir: Path) -> list[str]:
        return [str(self)]


@dataclasses.dataclass(frozen=True)
class LocalRequirement(Requirement):
    """Represents a requirement on a local project on the filesystem.

    The string format of a local requirement is `name@path`. The `name` must match the distribution name."""

    name: str
    path: Path

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(f"invalid requirement: {self}")

    def __str__(self) -> str:
        return f"{self.name} @ {self.path}"

    def to_args(self, base_dir: Path) -> list[str]:
        return [str((base_dir / self.path if base_dir else self.path).absolute())]


@dataclasses.dataclass(frozen=True)
class UrlRequirement(Requirement):
    """Represents a requirement that is installed from a URL."""

    name: str
    url: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(f"invalid requirement: {self}")
        print(self.url)
        if not urlparse(self.url).scheme:
            raise ValueError(f"invalid URL requirement: {self}")

    def __str__(self) -> str:
        return f"{self.name} @ {self.url}"

    def to_args(self, base_dir: Path) -> list[str]:
        return [str(self)]


@dataclasses.dataclass(frozen=True)
class RequirementSpec:
    """Represents the requirements for a kraken build script."""

    requirements: tuple[Requirement, ...]
    index_url: "str | None" = None
    extra_index_urls: tuple[str, ...] = ()
    interpreter_constraint: "str | None" = None
    pythonpath: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for req in self.requirements:
            assert isinstance(req, Requirement), type(req)

    def __eq__(self, other: Any) -> bool:
        # NOTE (@NiklasRosenstein): packaging.requirements.Requirement is not properly equality comparable, so
        #       we implement a custom comparison based on the hash digest.
        if isinstance(other, RequirementSpec):
            return (type(self), self.to_hash()) == (type(other), other.to_hash())
        return False

    def with_requirements(self, reqs: Iterable["str | Requirement"]) -> "RequirementSpec":
        """Adds the given requirements and returns a new instance."""

        requirements = list(self.requirements)
        for req in reqs:
            if isinstance(req, str):
                req = parse_requirement(req)
            requirements.append(req)

        return self.replace(requirements=tuple(requirements))

    def with_pythonpath(self, path: Iterable[str]) -> "RequirementSpec":
        """Adds the given pythonpath and returns a new instance."""

        return self.replace(pythonpath=(*self.pythonpath, *path))

    def replace(
        self,
        requirements: "Iterable[Requirement] | None" = None,
        index_url: "str | None | NotSet" = NotSet.Value,
        extra_index_urls: "Iterable[str] | None" = None,
        interpreter_constraint: "str | None | NotSet" = NotSet.Value,
        pythonpath: "Iterable[str] | None" = None,
    ) -> "RequirementSpec":
        return RequirementSpec(
            requirements=self.requirements if requirements is None else tuple(requirements),
            index_url=self.index_url if index_url is NotSet.Value else index_url,
            extra_index_urls=self.extra_index_urls if extra_index_urls is None else tuple(extra_index_urls),
            interpreter_constraint=self.interpreter_constraint
            if interpreter_constraint is NotSet.Value
            else interpreter_constraint,
            pythonpath=self.pythonpath if pythonpath is None else tuple(pythonpath),
        )

    @staticmethod
    def from_json(data: dict[str, Any]) -> "RequirementSpec":
        return RequirementSpec(
            requirements=tuple(parse_requirement(x) for x in data["requirements"]),
            index_url=data.get("index_url"),
            extra_index_urls=tuple(data.get("extra_index_urls", ())),
            interpreter_constraint=data.get("interpreter_constraint"),
            pythonpath=tuple(data.get("pythonpath", ())),
        )

    def to_json(self) -> dict[str, Any]:
        result: dict[str, Any] = {"requirements": [str(x) for x in self.requirements], "pythonpath": self.pythonpath}
        if self.index_url is not None:
            result["index_url"] = self.index_url
        if self.extra_index_urls:
            result["extra_index_urls"] = self.extra_index_urls
        if self.interpreter_constraint:
            result["interpreter_constraint"] = self.interpreter_constraint
        return result

    @staticmethod
    def from_args(args: list[str]) -> "RequirementSpec":
        """Parses the arguments using :mod:`argparse` as if they are Pip install arguments.

        :raise ValueError: If an invalid argument is encountered."""

        parser = argparse.ArgumentParser()
        parser.add_argument("packages", nargs="*")
        parser.add_argument("--index-url")
        parser.add_argument("--extra-index-url", action="append")
        parser.add_argument("--interpreter-constraint")
        parsed, unknown = parser.parse_known_args(args)
        if unknown:
            raise ValueError(f"encountered unknown arguments in requirements: {unknown}")

        return RequirementSpec(
            requirements=tuple(parse_requirement(x) for x in parsed.packages or []),
            index_url=parsed.index_url,
            extra_index_urls=tuple(parsed.extra_index_url or ()),
            interpreter_constraint=parsed.interpreter_constraint,
        )

    def to_args(
        self,
        base_dir: Path = Path("."),
        with_options: bool = True,
        with_requirements: bool = True,
    ) -> list[str]:
        """Converts the requirements back to Pip install arguments.

        :param base_dir: The base directory that relative :class:`LocalRequirement`s should be considered relative to.
        :param with_requirements: Can be set to `False` to not return requirements in the argument, just the index URLs.
        """

        args = []
        if with_options and self.index_url:
            args += ["--index-url", self.index_url]
        if with_options:
            for url in self.extra_index_urls:
                args += ["--extra-index-url", url]
        if with_requirements:
            args += flatten(req.to_args(base_dir) for req in self.requirements)
        return args

    def to_hash(self, algorithm: str = "sha256") -> str:
        """Hash the requirements spec to a hexdigest."""

        hash_parts = [str(req) for req in self.requirements] + ["::pythonpath"] + list(self.pythonpath)
        hash_parts += ["::interpreter_constraint", self.interpreter_constraint or ""]
        return hashlib.new(algorithm, ":".join(hash_parts).encode()).hexdigest()

    @classmethod
    def from_metadata(cls, metadata: BuildscriptMetadata) -> "RequirementSpec":
        return RequirementSpec(
            requirements=tuple(map(parse_requirement, metadata.requirements)),
            index_url=metadata.index_url,
            extra_index_urls=tuple(metadata.extra_index_urls),
            interpreter_constraint=DEFAULT_INTERPRETER_CONSTRAINT,
            pythonpath=tuple(metadata.additional_sys_paths) + (DEFAULT_BUILD_SUPPORT_FOLDER,),
        )

    def to_metadata(self) -> BuildscriptMetadata:
        return BuildscriptMetadata(
            index_url=self.index_url,
            extra_index_urls=list(self.extra_index_urls),
            requirements=[str(x) for x in self.requirements],
            additional_sys_paths=[x for x in self.pythonpath if x != DEFAULT_BUILD_SUPPORT_FOLDER],
        )
