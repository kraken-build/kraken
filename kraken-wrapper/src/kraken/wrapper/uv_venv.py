from __future__ import annotations

import logging
import os
import subprocess
from os import fsdecode, fspath
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable, MutableMapping, NamedTuple, Sequence

import tomli_w
from uv.__main__ import find_uv_bin

from kraken.common._fs import safe_rmpath
from kraken.common._requirements import (
    DEFAULT_INTERPRETER_CONSTRAINT,
    LocalRequirement,
    PipRequirement,
    RequirementSpec,
    UrlRequirement,
)
from kraken.common.findpython import get_python_interpreter_version
from kraken.common.path import is_relative_to
from kraken.common.sanitize import sanitize_http_basic_auth

logger = logging.getLogger(__name__)
UV_BIN = fsdecode(os.getenv("KRAKEN_UV_BIN", find_uv_bin()))

__all__ = ["PinnedRequirement", "UvVirtualEnv"]


class PinnedRequirement(NamedTuple):
    name: str
    version: str


class UvVirtualEnv:
    """
    A helper class that provides a programmatic API to interact with a virtual environment by calling to the Uv binary.
    """

    def __init__(self, path: Path, uv_bin: Path | None = None) -> None:
        """
        :param path: The path where the virtual environment is located.
        :param uv_bin: Path to the Uv binary. If not specified, defaults to the one that is installed alongside
            kraken-wrapper (as it depends on Uv).
        """

        self.path = path
        self.uv_bin = uv_bin or Path(UV_BIN)
        self.success_marker = self.path / ".success.flag"

        if os.name == "nt":
            self.bin_dir = self.path / "Scripts"
        else:
            self.bin_dir = self.path / "bin"

        self.python_bin = self.program("python")

    def exists(self) -> bool:
        return self.path.is_dir()

    def remove(self) -> None:
        safe_rmpath(self.path)

    def is_success_marker_set(self) -> bool:
        return self.success_marker.is_file()

    def set_success_marker(self, state: bool) -> None:
        if state:
            self.success_marker.parent.mkdir(exist_ok=True, parents=True)
            self.success_marker.touch()
        else:
            self.success_marker.unlink(missing_ok=True)

    def version(self) -> str:
        return get_python_interpreter_version(str(self.python_bin))

    def try_version(self) -> str | None:
        try:
            return self.version()
        except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError):
            return None

    def program(self, program: str) -> Path:
        path = self.bin_dir / program
        if os.name == "nt":
            path = path.with_name(path.name + ".exe")
        return path

    def create(self, *, python: Path | None) -> None:
        """
        Create a virtual environment at the specified path.
        """

        command = [os.fspath(self.uv_bin), "venv", str(self.path), "--no-config"]
        if python is not None:
            command.append("--python")
            command.append(os.fspath(python))
        logger.debug("Creating virtual environment at path '%s' using UV (%s)", self.path, self.uv_bin)
        subprocess.check_call(command)

    def install(
        self,
        *,
        requirements: Iterable[str],
        index_url: str | None = None,
        extra_index_urls: Sequence[str] = (),
        python_version: str | None = None,
        upgrade: bool = False,
    ) -> None:
        """
        Performs an exact install of the given requirements into the environment.
        """

        command = [
            os.fspath(self.uv_bin),
            "pip",
            "install",
            "--python",
            os.fspath(self.python_bin),
            "--exact",
            "--no-config",
        ]
        if index_url:
            command += ["--index-url", index_url]
        for url in extra_index_urls:
            command += ["--extra-index-url", url]
        if python_version:
            command += ["--python-version", python_version]
        if upgrade:
            command += ["--upgrade"]
        command += ["--"]
        command += requirements

        logger.debug("Installing into build environment with uv: %s", sanitize_http_basic_auth(" ".join(command)))
        subprocess.check_call(command)

    def freeze(self) -> list[PinnedRequirement]:
        """
        Returns the exact versions of requirements installed in the environment, except editable requirements.
        """

        command = [
            os.fspath(self.uv_bin),
            "pip",
            "freeze",
            "--no-config",
            "--python",
            os.fspath(self.python_bin),
            "--exclude-editable",
        ]

        requirements_txt = subprocess.check_output(command).decode()
        return [
            PinnedRequirement(line[0], line[1])
            for line in map(lambda req: req.split("=="), requirements_txt.splitlines())
        ]

    def install_pth_file(self, filename: str, pythonpath: list[str]) -> None:
        """
        Installs the additional `sys.path` paths given with *pythonpath* into the virtual environment, replacing any
        existing configuration that might have been installed by a previous call to this function for the same environment.
        """

        # Inspect the environment's sysconfig.
        command = [os.fspath(self.python_bin), "-c", "from sysconfig import get_path; print(get_path('purelib'))"]
        site_packages = Path(subprocess.check_output(command).decode().strip())

        pth_file = site_packages / filename
        if pythonpath:
            logger.debug("Writing .pth file at %s", pth_file)
            pth_file.write_text("\n".join(os.fspath(Path(path).absolute()) for path in pythonpath))
        elif pth_file.is_file():
            logger.debug("Removing .pth file at %s", pth_file)
            pth_file.unlink()

    def activate(self, environ: MutableMapping[str, str]) -> None:
        environ["PATH"] = os.fspath(self.bin_dir.absolute()) + os.pathsep + environ["PATH"]
        environ["VIRTUAL_ENV"] = os.fspath(self.path.absolute())
        environ["VIRTUAL_ENV_PROMPT"] = f"({self.path.name})"

    def deactivate(self, environ: MutableMapping[str, str]) -> None:
        environ.pop("VIRTUAL_ENV", None)
        environ.pop("VIRTUAL_ENV_PROMPT", None)

        # Remove entries from the PATH that point inside the virtual environment.
        paths = environ.get("PATH", "").split(os.pathsep)
        paths = [path for path in paths if not is_relative_to(Path(path), self.path)]
        environ["PATH"] = os.pathsep.join(paths)


class UvProjectShim:
    """
    Helper class that acts like a proper Python project to get Uv to generate a lock file
    and install into a virtual environment.
    """

    def __init__(self, project_name: str = "kraken-build-env", version: str = "0.0.0") -> None:
        self._tempdir: TemporaryDirectory[str] | None = None
        self.project_name = project_name
        self.version = version

    def __enter__(self) -> UvProjectShim:
        self._tempdir = TemporaryDirectory()
        self._tempdir.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        assert self._tempdir is not None
        self._tempdir.__exit__(*args)

    @staticmethod
    def generate_pyproject_toml(
        base_dir: Path,
        project_name: str,
        version: str,
        requirements: RequirementSpec,
    ) -> dict[str, Any]:
        """
        Generates the payload for a `pyproject.toml`.

        Args:
            base_dir: The base directory where local, relative requirements are considered relative to.
            project_name: The name to put into the `[project]` section.
            version: The version to put into the `[project]` section.
            requirements: The requirements. All fields but the `pythonpath` are taken into account.
        """

        payload = {
            "project": {
                "name": project_name,
                "version": version,
                "dependencies": (dependencies := []),
                "requires-python": requirements.interpreter_constraint or DEFAULT_INTERPRETER_CONSTRAINT,
            },
            "tool": {
                "uv": {
                    "sources": (sources := {}),
                    "index": (indexes := []),
                }
            },
        }

        for req in requirements.requirements:
            match req:
                case PipRequirement():
                    dependencies.append(str(req))
                case LocalRequirement() | UrlRequirement():
                    dependencies.append(req.name)
                    sources[req.name] = req.to_uv_source(base_dir)
                case _:
                    assert False, f"unexpected requirement type: {type(req).__name__} - {req!r}"

        if requirements.index_url:
            indexes.append({"url": requirements.index_url, "default": True})

        for url in requirements.extra_index_urls:
            indexes.append({"url": url})

        return payload

    def write_pyproject_toml(self, base_dir: Path, requirements: RequirementSpec) -> None:
        payload = self.generate_pyproject_toml(base_dir, self.project_name, self.version, requirements)
        self.pyproject_toml().write_text(tomli_w.dumps(payload))

    def sync(self, venv: UvVirtualEnv) -> None:
        """Run `uv sync` for the project."""

        assert self._tempdir is not None, "context not entered"

        command = [
            "uv",
            "sync",
            "--project",
            self._tempdir.name,
            "--python",
            fspath(venv.python_bin),
            "--fork-strategy",
            "fewest",
        ]
        logger.debug("Installing into build environment with uv: %s", sanitize_http_basic_auth(" ".join(command)))
        subprocess.check_call(
            command,
            cwd=self._tempdir.name,
            env={k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
            | {"UV_PROJECT_ENVIRONMENT": fspath(venv.path)},
        )

    def lock(self, venv: UvVirtualEnv) -> None:
        """Run `uv lock` for the project."""

        assert self._tempdir is not None, "context not entered"

        command = ["uv", "lock", "--project", self._tempdir.name, "--python", fspath(venv.python_bin)]
        logger.debug("Locking build environment with uv: %s", sanitize_http_basic_auth(" ".join(command)))
        subprocess.check_call(
            command,
            cwd=self._tempdir.name,
            env={k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
            | {"UV_PROJECT_ENVIRONMENT": fspath(venv.path)},
        )

    def pyproject_toml(self) -> Path:
        """Return the path to the pyproject.toml file."""

        assert self._tempdir is not None, "context not entered"
        return Path(self._tempdir.name).joinpath("pyproject.toml")

    def lockfile(self) -> Path:
        """Return the path to the Uv lockfile."""

        assert self._tempdir is not None, "context not entered"
        return Path(self._tempdir.name).joinpath("uv.lock")
