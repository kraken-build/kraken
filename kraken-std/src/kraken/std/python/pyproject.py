from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, MutableMapping, cast

import tomli
import tomli_w


@dataclass
class Pyproject(MutableMapping[str, Any]):
    _path: Path
    _data: dict[str, Any]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    @classmethod
    def read(cls, path: Path) -> Pyproject:
        with path.open("rb") as fp:
            return cls.of(path, tomli.load(fp))

    @classmethod
    def of(cls, path: Path, data: dict[str, Any]) -> Pyproject:
        return Pyproject(path, data)

    def to_json(self) -> dict[str, Any]:
        return self._data

    def to_toml_string(self) -> str:
        return tomli_w.dumps(self.to_json())

    def save(self, path: Path | None = None) -> None:
        path = path or self._path
        with path.open("wb") as fp:
            tomli_w.dump(self.to_json(), fp)

    def set_core_metadata_version(self, version: str | None) -> str | None:
        """Updates the core metadata version field and returns the previous value"""
        return self._set_version(self.setdefault("project", {}), version)

    @staticmethod
    def _set_version(config: Any, version: str | None) -> str | None:
        """Updates the core metadata version field and returns the previous value"""
        old_version = config.get("version")
        if version is None:
            if "version" in config:
                del config["version"]
        else:
            config["version"] = version
        return old_version  # type: ignore[no-any-return]

    def _tool_section(self, name: str) -> Dict[str, Any]:
        return self.setdefault("tool", {}).setdefault(name, {})  # type: ignore[no-any-return]

    def _get_pyproj_sources(self, sources_conf: Dict[str, Any]) -> list[dict[str, Any]]:
        return list(sources_conf.setdefault("source", []))

    def _delete_pyproj_source(self, sources_conf: list[dict[str, Any]], source_name: str) -> None:
        index = [conf["name"] for conf in sources_conf].index(source_name)
        del sources_conf[index]

    def _find_dependencies_definitions(self, pyproject_section: Dict[str, Any], version: str) -> None:
        """
        Finds and updates the version of local dependencies listed in the
        "dev-dependencies" and "dependencies" sections of the PyProject.toml file.
        Args:
            pyproject_section (Dict[str, Any]): A dictionary representing a section of the PyProject.toml file.
            version (str): The version to update local dependencies with.
        """

        # TODO(@niklas.rosenstein): Support Poetry dependency groups
        #       https://python-poetry.org/docs/master/managing-dependencies/#dependency-groups

        for key, value in pyproject_section.items():
            if key in ("dependencies", "dev-dependencies"):
                if type(value) == dict:
                    self._update_dependencies_version(value, version)
                pass
            else:
                if type(value) is dict:
                    self._find_dependencies_definitions(value, version)

    def _update_dependencies_version(self, obj: Dict[str, Any], version: str) -> None:
        for _key, value in obj.items():
            if type(value) == dict:
                if "path" in value and "develop" in value:
                    del value["path"]
                    del value["develop"]
                    value["version"] = version


class SpecializedPyproject(ABC):
    """Builder specific operations"""

    def __init__(self, pyproj: Pyproject) -> None:
        self._pyproj = pyproj

    def set_version(self, version: str | None) -> str | None:
        """Updates the poetry version field and returns the previous value"""
        return self._pyproj._set_version(self._get_section(), version)

    @abstractmethod
    def _get_section(self) -> Dict[str, Any]:
        pass

    def get_sources(self) -> list[dict[str, Any]]:
        return list(self._get_section().setdefault("source", []))

    def delete_source(self, source_name: str) -> None:
        return self._pyproj._delete_pyproj_source(self.get_sources(), source_name)

    def update_relative_packages(self, version: str) -> None:
        self._pyproj._find_dependencies_definitions(self._get_section(), version)

    def save(self, path: Path | None = None) -> None:
        self._pyproj.save(path)

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_version(self) -> str | None:
        pass

    @abstractmethod
    def upsert_source(self, source_name: str, url: str, default: bool = False, secondary: bool = False) -> None:
        pass


class PDMPyproject(SpecializedPyproject):
    """PDM specific operations"""

    def __init__(self, pyproj: Pyproject) -> None:
        super().__init__(pyproj)

    def _get_section(self) -> Dict[str, Any]:
        return self._pyproj._tool_section("pdm")

    def get_name(self) -> str:
        return cast(str, self._pyproj["project"]["name"])

    def get_version(self) -> str | None:
        return cast(str, self._pyproj["project"].get("requires-python", None))

    def upsert_source(self, source_name: str, url: str, _default: bool = False, _secondary: bool = False) -> None:
        sources_conf = self.get_sources()
        source_config: dict[str, Any] = {"name": source_name, "url": url}

        # Find the source with the same name and update it, or create a new one.
        source = next((x for x in sources_conf if x["name"] == source_name), None)
        if source is None:
            sources_conf.append(source_config)
        else:
            source.update(source_config)


class PoetryPyproject(SpecializedPyproject):
    """Poetry specific operations"""

    def __init__(self, pyproj: Pyproject) -> None:
        super().__init__(pyproj)

    def get_name(self) -> str:
        return cast(str, self._pyproj["tool"]["poetry"]["name"])

    def get_version(self) -> str | None:
        return cast(str, self._pyproj.get("tool", {}).get("poetry", {}).get("dependencies", {}).get("python"))

    def _get_section(self) -> Dict[str, Any]:
        return self._pyproj._tool_section("poetry")

    def get_packages(self, fallback: bool = True) -> list[PoetryPackageInfo]:
        """
        Returns the information stored in `[tool.poetry.packages]` configuration. If that configuration does not
        exist and *fallback* is set to True, the default that Poetry will assume is returned.
        """

        packages: list[dict[str, Any]] | None = self._get_section().get("packages")
        if packages is None and fallback:
            package_name = self._get_section()["name"]
            return [PoetryPackageInfo(include=package_name.replace("-", "_").replace(".", "_"))]
        else:
            return [PoetryPackageInfo(include=x["include"], from_=x.get("from")) for x in packages or ()]

    def synchronize_project_section_to_poetry_state(self) -> None:
        poetry_section = self._get_section()
        project_section = self._pyproj.setdefault("project", {})
        for field_name in ("name", "version"):
            poetry_value = poetry_section.get(field_name)
            project_value = project_section.get(field_name)
            if poetry_value == project_value:
                continue
            elif poetry_value is None:
                poetry_section[field_name] = project_value
            else:
                project_section[field_name] = poetry_value

    def upsert_source(self, source_name: str, url: str, default: bool = False, secondary: bool = False) -> None:
        sources_conf = self.get_sources()
        source_config: dict[str, Any] = {"name": source_name, "url": url}
        if default:
            source_config["default"] = True
        if secondary:
            source_config["secondary"] = True

        # Find the source with the same name and update it, or create a new one.
        source = next((x for x in sources_conf if x["name"] == source_name), None)
        if source is None:
            sources_conf.append(source_config)
        else:
            source.update(source_config)


@dataclass
class PoetryPackageInfo:
    include: str
    from_: str | None = None
