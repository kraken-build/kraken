from __future__ import annotations

import logging
import os
import subprocess
from os import fsdecode
from pathlib import Path
from typing import Iterable, MutableMapping, NamedTuple, Sequence

from uv.__main__ import find_uv_bin

from kraken.common._fs import safe_rmpath
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
