"""Activate or de-activate a Python virtual environment by updating environment variables."""

import dataclasses
import os
import subprocess as sp
from collections.abc import MutableMapping
from pathlib import Path

from kraken.common.path import is_relative_to


@dataclasses.dataclass
class VirtualEnvInfo:
    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    def exists(self) -> bool:
        return self.path.exists()

    def get_bin_directory(self) -> Path:
        if os.name == "nt":
            return self.path / "Scripts"
        else:
            return self.path / "bin"

    def get_bin(self, program: str) -> Path:
        path = self.get_bin_directory() / program
        if os.name == "nt":
            path = path.with_name(path.name + ".exe")
        return path

    def get_python_version(self) -> str:
        return sp.check_output([self.get_bin("python"), "-c", "import sys; print(sys.version)"]).decode().strip()

    def activate(self, environ: MutableMapping[str, str]) -> None:
        environ["PATH"] = str(self.get_bin_directory().absolute()) + os.pathsep + environ["PATH"]
        environ["VIRTUAL_ENV"] = str(self.path.absolute())
        environ["VIRTUAL_ENV_PROMPT"] = f"({self.path.name})"

    def deactivate(self, environ: MutableMapping[str, str]) -> None:
        environ.pop("VIRTUAL_ENV", None)
        environ.pop("VIRTUAL_ENV_PROMPT", None)

        # Remove entries from the PATH that point inside the virtual environment.
        paths = environ.get("PATH", "").split(os.pathsep)
        paths = [path for path in paths if not is_relative_to(Path(path), self.path)]
        environ["PATH"] = os.pathsep.join(paths)


def get_current_venv(environ: MutableMapping[str, str]) -> VirtualEnvInfo | None:
    """Check the environment variables in *environ* for a `VIRTUAL_ENV` variable."""

    venv_path = environ.get("VIRTUAL_ENV")
    if venv_path:
        return VirtualEnvInfo(Path(venv_path))
    return None
