"""Manifest parser for the relevant bits and pieces of proto tomls."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli
import tomli_w

logger = logging.getLogger(__name__)


@dataclass
class BuffrsManifest:
    _path: Path
    _data: dict[str, Any]

    package: Package | None

    @classmethod
    def read(cls, path: Path) -> BuffrsManifest:
        with path.open("rb") as fp:
            return cls.of(path, tomli.load(fp))

    @classmethod
    def of(cls, path: Path, data: dict[str, Any]) -> BuffrsManifest:
        package = data.get("package")
        return cls(
            path,
            data,
            package=Package.from_json(package) if package is not None else None,
        )

    def to_json(self) -> dict[str, Any]:
        result = self._data.copy()

        if self.package:
            result["package"] = self.package.to_json()

        return result

    def to_toml_string(self) -> str:
        return tomli_w.dumps(self.to_json())

    def save(self, path: Path | None = None) -> None:
        path = path or self._path
        with path.open("wb") as fp:
            tomli_w.dump(self.to_json(), fp)


@dataclass
class Package:
    type_: str
    name: str
    version: str
    unhandled: dict[str, Any]

    @classmethod
    def from_json(cls, json: dict[str, str]) -> Package:
        cloned = dict(json)
        type_ = cloned.pop("type")
        name = cloned.pop("name")
        version = cloned.pop("version")
        return Package(type_, name, version, cloned)

    def to_json(self) -> dict[str, str]:
        values = {"type": self.type_, "name": self.name, "version": self.version}

        if self.unhandled is not None:
            values.update({k: v for k, v in self.unhandled.items() if v is not None})

        return {k: v for k, v in values.items() if v is not None}
