from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    import rich.table

logger = logging.getLogger(__name__)
DEFAULT_CACHE_PATH = Path("~/.cache/krakenw/python-interpreters.json")


class InterpreterCandidate(TypedDict):
    path: str
    min_version: NotRequired[str | None]
    exact_version: NotRequired[str | None]


class Interpreter(TypedDict):
    path: str  # absolute path
    version: str  # x.y.z
    selected: NotRequired[bool]


class InterpreterVersionCache:
    """
    Helper class to cache the version of Python interpreters.
    """

    class _CacheEntry(TypedDict, total=True):
        md5sum: str
        version: str

    class _Payload(TypedDict, total=True):
        version: str
        paths: dict[str, InterpreterVersionCache._CacheEntry]

    EMPTY_PAYLOAD: ClassVar[_Payload] = {"version": "v1", "paths": {}}

    def __init__(self, file: Path = DEFAULT_CACHE_PATH) -> None:
        self.file = file.expanduser()
        self.cache: InterpreterVersionCache._Payload | None = None

    def _load(self) -> InterpreterVersionCache._Payload:
        if self.cache is None:
            if self.file.is_file():
                self.cache = json.loads(self.file.read_text())
            else:
                self.cache = copy.deepcopy(InterpreterVersionCache.EMPTY_PAYLOAD)
        return self.cache

    def _save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self._load()))

    def _hash_file(self, path: Path) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()

    def get_version(self, path: Path) -> str | None:
        try:
            path = path.resolve()
        except FileNotFoundError:
            return None
        cache = self._load()
        entry = cache["paths"].get(str(path))
        if entry is None or entry["md5sum"] != self._hash_file(path):
            return None
        return entry["version"]

    def set_version(self, path: Path, version: str) -> None:
        path = path.resolve()
        cache = self._load()
        cache["paths"][str(path)] = {"md5sum": self._hash_file(path), "version": version}
        self._save()


def get_candidates(
    path_list: Sequence[str | Path] | None = None, check_pyenv: bool = True
) -> Iterator[InterpreterCandidate]:
    """
    Finds all Python interpreters on the system. This function only finds possible candidates, it does not
    check whether the interpreter is actually valid or retrieve its actual version. The generator may yield
    duplicate results if there are multiple symlinks pointing to the same interpreter binary.

    If *path_list* is not specified, the current PATH is used. If *check_pyenv* is True, Python interpreters
    installed via pyenv are also included in the results.
    """

    if path_list is None:
        path_list = os.environ["PATH"].split(os.pathsep)

    commands: set[Path] = set()
    for path in map(Path, path_list):
        if not path.is_dir():
            continue
        for item in path.iterdir():
            if not (item.name.startswith("python") or item.name == "py"):
                continue
            try:
                if not item.is_file() or not os.access(item, os.X_OK):
                    continue
            except PermissionError:
                continue
            else:
                commands.add(item)

    # py and python
    for command in commands:
        if command.name in ("py", "python"):
            yield {"path": str(command)}

    # pythonX
    for command in commands:
        match = re.match(r"python(\d)$", command.name)
        if match:
            yield {
                "path": str(command),
                "min_version": f"{match.group(1)}.0.0" if match.group(1) else None,
            }

    # pythonX.Y
    for command in commands:
        match = re.match(r"python(\d\.\d\d?)$", command.name)
        if match:
            yield {"path": str(command), "min_version": f"{match.group(1)}.0"}

    # pythonX.Y.Z
    for command in commands:
        match = re.match(r"python(\d\.\d\d?\.\d\d?)$", command.name)
        if match:
            yield {"path": str(command), "exact_version": match.group(1)}

    # pyenv (+Windows)
    if check_pyenv:
        pyenv_versions = Path("~/.pyenv/versions").expanduser()
        if not pyenv_versions.is_dir():
            pyenv = os.getenv("PYENV")
            if pyenv:
                pyenv_versions = Path(pyenv).expanduser().joinpath("versions")
            elif os.name == "nt":
                pyenv_versions = Path("~/.pyenv/pyenv-win/versions").expanduser()
    else:
        pyenv_versions = None

    if pyenv_versions and pyenv_versions.is_dir():
        for item in pyenv_versions.iterdir():
            if re.match(r"\d+\.\d+\.\d+$", item.name) and item.is_dir():
                if os.name == "nt":
                    yield {"path": str(item / "python.exe"), "exact_version": item.name}
                else:
                    yield {"path": str(item / "bin" / "python"), "exact_version": item.name}

    yield {"path": sys.executable, "exact_version": ".".join(map(str, sys.version_info[:3]))}


def get_python_interpreter_version(python_bin: str) -> str:
    """
    Returns the version of the given Python interpreter by querying it with the `--version` option.

    Raises:
        RuntimeError: If the output of the command cannot be parsed.
        subprocess.CalledProcessError: If the command fails.
    """

    output = subprocess.check_output([python_bin, "--version"], stderr=subprocess.STDOUT, text=True)
    match = re.match(r"Python (\d+\.\d+\.\d+)", output)
    if not match:
        raise RuntimeError(f"Could not determine Python version from output: {output}")
    return match.group(1)


def evaluate_candidates(
    candidates: Iterable[InterpreterCandidate], cache: InterpreterVersionCache | None = None
) -> list[Interpreter]:
    """
    Evaluates Python interpreter candidates and returns the deduplicated list of interpreters that were found.
    """

    interpreters: list[Interpreter] = []
    visited: set[Path] = set()

    for choice in candidates:
        try:
            path = Path(choice["path"]).resolve()
        except FileNotFoundError:
            logger.debug("Python interpreter %s does not exist", choice["path"], exc_info=True)
            continue

        if path in visited:
            continue
        visited.add(path)

        version = cache.get_version(path) if cache else None
        if version is None:
            try:
                version = get_python_interpreter_version(str(path))
            except (subprocess.CalledProcessError, RuntimeError, FileNotFoundError):
                logger.debug("Failed to get version for Python interpreter %s", path, exc_info=True)
                continue
            if cache:
                cache.set_version(path, version)

        interpreter: Interpreter = {"path": str(path), "version": version}
        interpreters.append(interpreter)

    return interpreters


def build_rich_table(interpreters: Iterable[Interpreter]) -> rich.table.Table:
    """
    Gets a table of all viable Python interpreters on the system.

    Requires that the `rich` package is installed.
    """

    import rich.table

    tb = rich.table.Table("Path", "Version")
    for interpreter in interpreters:
        version = interpreter["version"]
        if interpreter.get("selected"):
            version += " *"
        tb.add_row(interpreter["path"], version)
    return tb


def match_version_constraint(constraint: str, version: str) -> bool:
    """
    Match a Python package version against a constraint.
    """

    from packaging.specifiers import SpecifierSet

    return SpecifierSet(constraint).contains(version)


def main() -> None:
    import argparse

    try:
        import rich
        import rich.table

        def tabulate(interpreters: Iterable[Interpreter]) -> None:
            rich.print(build_rich_table(interpreters))

    except ImportError:

        def tabulate(interpreters: Iterable[Interpreter]) -> None:
            for interpreter in interpreters:
                print(interpreter)

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--constraint", help="Find a Python interpreter with the given constraint.")
    args = parser.parse_args()

    interpreters = evaluate_candidates(get_candidates(), InterpreterVersionCache())

    if args.constraint:
        for interpreter in interpreters:
            if match_version_constraint(args.constraint, interpreter["version"]):
                interpreter["selected"] = True

    tabulate(interpreters)


if __name__ == "__main__":
    main()
