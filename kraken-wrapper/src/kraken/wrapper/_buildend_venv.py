import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, NoReturn

from kraken.common import EnvironmentType, RequirementSpec, safe_rmpath
from kraken.common.pyenv import VirtualEnvInfo

from ._buildenv import KRAKEN_MAIN_IMPORT_SNIPPET, BuildEnv, general_get_installed_distributions
from ._lockfile import Distribution

logger = logging.getLogger(__name__)


class VenvBuildEnv(BuildEnv):
    def __init__(self, path: Path, incremental: bool = False) -> None:
        self._path = path
        self._venv = VirtualEnvInfo(self._path)
        self._incremental = incremental

    # BuildEnv

    def get_path(self) -> Path:
        return self._path

    def get_type(self) -> EnvironmentType:
        return EnvironmentType.VENV

    def get_installed_distributions(self) -> List[Distribution]:
        python = self._venv.get_bin("python")
        return general_get_installed_distributions([str(python), "-c", f"{KRAKEN_MAIN_IMPORT_SNIPPET}\nmain()"])

    def build(self, requirements: RequirementSpec, transitive: bool) -> None:
        if not self._incremental and self._path.exists():
            logger.debug("Removing existing virtual environment at %s", self._path)
            safe_rmpath(self._path)

        python_bin = str(self._venv.get_bin("python"))

        if not self._path.exists():
            command = [sys.executable, "-m", "venv", str(self._path)]
            logger.debug("Creating virtual environment at %s: %s", self._path, " ".join(command))
            subprocess.check_call(command)

            # Upgrade Pip.
            command = [python_bin, "-m", "pip", "install", "--upgrade", "pip"]
            logger.debug("Upgrading Pip: %s", command)
            subprocess.check_call(command)

        else:
            logger.debug("Reusing virtual environment at %s", self._path)

        # Install requirements.
        command = [
            python_bin,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "--no-input",
        ]
        # Must enable transitive resolution because lock files are not currently cross platform (see kraken-wrapper#2).
        # if not transitive:
        #     command += ["--no-deps"]
        # TODO (@NiklasRosenstein): Handle requirements interpreter constraint (see kraken-wrapper#5).
        command += requirements.to_args()
        logger.debug("Installing into build environment with Pip: %s", " ".join(command))
        subprocess.check_call(command)

        # Make sure the pythonpath from the requirements is encoded into the enviroment.
        command = [python_bin, "-c", "from sysconfig import get_path; print(get_path('purelib'))"]
        site_packages = Path(subprocess.check_output(command).decode().strip())
        pth_file = site_packages / "krakenw.pth"
        if requirements.pythonpath:
            logger.debug("Writing .pth file at %s", pth_file)
            pth_file.write_text("\n".join(str(Path(path).absolute()) for path in requirements.pythonpath))
        elif pth_file.is_file():
            logger.debug("Removing .pth file at %s", pth_file)
            pth_file.unlink()

    def dispatch_to_kraken_cli(self, argv: List[str]) -> NoReturn:
        python = self._venv.get_bin("python")
        command = [str(python), "-c", f"{KRAKEN_MAIN_IMPORT_SNIPPET}\nmain()", *argv]
        env = os.environ.copy()
        self.get_type().set(env)
        env["PATH"] = str(self._venv.get_bin_directory()) + os.pathsep + env.get("PATH", "")
        sys.exit(subprocess.call(command, env=env))
