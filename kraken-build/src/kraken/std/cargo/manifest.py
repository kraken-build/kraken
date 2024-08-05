"""Manifest parser for the relevant bits and pieces."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Any

import tomli
import tomli_w

logger = logging.getLogger(__name__)


@dataclass
class Bin:
    name: str
    path: str
    _remainder: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "path": self.path, **self._remainder}

    @staticmethod
    def from_json(data: dict[str, Any]) -> Bin:
        data = dict(data)
        return Bin(data.pop("name"), data.pop("path"), _remainder=data)


# TODO: Differentiate between lib kinds?


class ArtifactKind(Enum):
    BIN = 1
    LIB = 2


@dataclass
class Artifact:
    name: str
    path: str
    kind: ArtifactKind
    manifest_path: str

    def to_json(self) -> dict[str, str]:
        return {"name": self.name, "path": self.path, "kind": str(self.kind), "manifest_path": self.manifest_path}


@dataclass
class WorkspaceMember:
    id: str
    name: str
    version: str
    edition: str
    manifest_path: Path


@dataclass
class CargoMetadata:
    _path: Path
    _data: dict[str, Any]

    workspaceMembers: list[WorkspaceMember]
    artifacts: list[Artifact]
    target_directory: Path

    @classmethod
    def read(cls, project_dir: Path, from_project_dir: bool = False, locked: bool | None = None) -> CargoMetadata:
        cmd = [
            "cargo",
            "metadata",
            "--no-deps",
            "--format-version=1",
            "--manifest-path",
            str(project_dir / "Cargo.toml"),
        ]

        # the .cargo/config.toml in user/foo/bar is not picked up when running this command from
        # user/foo for example. This flag executes the subprocess from the project dir
        if from_project_dir:
            cwd = project_dir
        else:
            cwd = Path(os.getcwd())

        if locked is None:
            # Append `--locked` if a Cargo.lock file is found in the project directory or any of its parents.
            project_dir = project_dir.absolute()
            for parent in [project_dir, *project_dir.parents]:
                if (parent / "Cargo.lock").exists():
                    cmd.append("--locked")
                    break
        elif locked:
            # If locked is True, we should *always* pass --locked. The expectation is that the command will
            # fail w/o a Cargo.lock file.
            cmd.append("--locked")

        result = subprocess.run(cmd, stdout=subprocess.PIPE, cwd=cwd)

        if result.returncode != 0:
            logger.error("Stderr: %s", result.stderr)
            logger.error(f"Could not execute `{' '.join(cmd)}`, and thus can't read the cargo metadata.")
            logger.error(
                "This is due to a malformed Cargo setup, possibly due to missing registries in the config.toml."
                "See https://github.com/kraken-build/kraken-std/pull/59 for more details."
            )
            logger.error(
                "This is a known deficiency of Kraken currently - to proceed, you must comment out "
                "non-default registry imports that you have added in your Cargo.toml files, run "
                "`krakenw run :cargoSyncConfig`, and then uncomment them again."
            )
            logger.error(
                "If you continue to have this error after performing the above, you may have unrelated Cargo issues"
            )
            raise RuntimeError("Could not read cargo metadata. Please see logs for instructions.")
        else:
            return cls.of(project_dir, json.loads(result.stdout.decode("utf-8")))

    @classmethod
    def of(cls, path: Path, data: dict[str, Any]) -> CargoMetadata:
        workspace_members = []
        artifacts = []
        for package in data["packages"]:
            id = package["id"]
            if id in data["workspace_members"]:
                workspace_members.append(
                    WorkspaceMember(
                        id, package["name"], package["version"], package["edition"], Path(package["manifest_path"])
                    )
                )
                for target in package["targets"]:
                    if "bin" in target["kind"]:
                        artifacts.append(
                            Artifact(target["name"], target["src_path"], ArtifactKind.BIN, package["manifest_path"])
                        )
                    elif "lib" in target["kind"]:
                        artifacts.append(
                            Artifact(target["name"], target["src_path"], ArtifactKind.LIB, package["manifest_path"])
                        )

        return cls(path, data, workspace_members, artifacts, Path(data["target_directory"]))


@dataclass
class Package:
    name: str
    version: str | None
    edition: str | None
    unhandled: dict[str, Any] | None

    @classmethod
    def from_json(cls, json: dict[str, str]) -> Package:
        cloned = dict(json)
        name = cloned.pop("name")
        version = cloned.pop("version", None)
        edition = cloned.pop("edition", None)
        return Package(name, version, edition, cloned)

    def to_json(self) -> dict[str, str]:
        values = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "unhandled"}
        if self.unhandled is not None:
            values.update({k: v for k, v in self.unhandled.items() if v is not None})
        return {k: v for k, v in values.items() if v is not None}


@dataclass
class WorkspacePackage:
    version: str
    unhandled: dict[str, Any] | None

    @classmethod
    def from_json(cls, json: dict[str, str]) -> WorkspacePackage:
        cloned = dict(json)
        version = cloned.pop("version")
        return WorkspacePackage(version, cloned)

    def to_json(self) -> dict[str, str]:
        values = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "unhandled"}
        if self.unhandled is not None:
            values.update({k: v for k, v in self.unhandled.items() if v is not None})
        return {k: v for k, v in values.items() if v is not None}


@dataclass
class Workspace:
    package: WorkspacePackage | None
    members: list[str] | None
    unhandled: dict[str, Any] | None

    @classmethod
    def from_json(cls, json: dict[str, Any]) -> Workspace:
        cloned = dict(json)
        return Workspace(
            WorkspacePackage.from_json(cloned.pop("package")) if "package" in cloned else None,
            cloned.pop("members") if "members" in cloned else None,
            cloned,
        )

    def to_json(self) -> dict[str, Any]:
        values = {
            "package": self.package.to_json() if self.package else None,
            "members": self.members if self.members else None,
        }
        if self.unhandled is not None:
            values.update({k: v for k, v in self.unhandled.items() if v is not None})
        return {k: v for k, v in values.items() if v is not None}


@dataclass
class Dependencies:
    data: dict[str, Any]

    @classmethod
    def from_json(cls, json: dict[str, Any]) -> Dependencies:
        cloned = dict(json)
        return Dependencies(cloned)

    def to_json(self) -> dict[str, Any]:
        return self.data


@dataclass
class CargoManifest:
    _path: Path
    _data: dict[str, Any]

    package: Package | None
    workspace: Workspace | None
    dependencies: Dependencies | None
    build_dependencies: Dependencies | None
    bin: list[Bin]

    @classmethod
    def read(cls, path: Path) -> CargoManifest:
        with path.open("rb") as fp:
            ret = cls.of(path, tomli.load(fp))
            if ret.package is None and ret.workspace is None:
                raise ValueError("Cargo manifest must have either a package or a workspace section.")
            return ret

    @classmethod
    def of(cls, path: Path, data: dict[str, Any]) -> CargoManifest:
        return cls(
            path,
            data,
            Package.from_json(data["package"]) if "package" in data else None,
            Workspace.from_json(data["workspace"]) if "workspace" in data else None,
            Dependencies.from_json(data["dependencies"]) if "dependencies" in data else None,
            Dependencies.from_json(data["build-dependencies"]) if "build-dependencies" in data else None,
            [Bin.from_json(x) for x in data.get("bin", [])],
        )

    def to_json(self) -> dict[str, Any]:
        result = self._data.copy()
        if self.bin:
            result["bin"] = [x.to_json() for x in self.bin]
        else:
            result.pop("bin", None)
        if self.package:
            result["package"] = self.package.to_json()
        if self.workspace:
            result["workspace"] = self.workspace.to_json()
        if self.dependencies:
            result["dependencies"] = self.dependencies.to_json()
        if self.build_dependencies:
            result["build-dependencies"] = self.build_dependencies.to_json()
        return result

    def to_toml_string(self) -> str:
        return tomli_w.dumps(self.to_json())

    def save(self, path: Path | None = None) -> None:
        path = path or self._path
        with path.open("wb") as fp:
            tomli_w.dump(self.to_json(), fp)
