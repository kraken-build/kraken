import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import databind.json
from adjudicator import collect_rules, get, rule

from kraken.targets.goals import InstallGoal
from kraken.targets.python.binary import PythonBinary, PythonBinaryRequest
from kraken.targets.rulerunner import RuleRunner
from kraken.targets.target import make_target_factory

logger = logging.getLogger(__name__)

##
# CreateVenv Rule
##


@dataclass(frozen=True)
class CreateVenvRequest:
    """
    A request for creating a Python virtual environment.
    """

    #: The path where the virtual environment should be created.
    path: Path

    #: A constraint for the Python interpreter to use when creating the virtual environment.
    #: This is ignored if a #python is specified.
    interpreter_constraint: str | None = None

    #: The Python binary to create the virtual environment with.
    python: PythonBinary | None = None


@dataclass(frozen=True)
class CreateVenvResponse:
    """
    A response for creating a Python virtual environment.
    """

    #: The path to the Python binary of the virtual environment.
    python: PythonBinary

    #: Path to the virtual environment's bin/Scripts folder.
    scripts_dir: Path


@rule
def create_venv(request: CreateVenvRequest) -> CreateVenvResponse:
    python = request.python or get(
        PythonBinary,
        PythonBinaryRequest(interpreter_constraint=request.interpreter_constraint),
    )

    path = request.path
    metadata_file = path / ".metadata"

    if path.is_dir():
        # Check if the virtual environment was created using the correct PythonBinary.
        metadata: PythonBinary | None = None
        if metadata_file.is_file():
            try:
                metadata = databind.json.loads(metadata_file.read_text(), PythonBinary)
            except Exception:
                logger.warning(
                    f"Failed to read metadata file {metadata_file}. The virtual environment at "
                    f"{path} will be recreated."
                )

        if not metadata:
            recreate = True
            logger.info(
                f"Recreating virtual environment at {path} because it was created with an unknown Python version."
            )
        elif metadata != python:
            recreate = True
            logger.info(
                f"Recreating virtual environment at {path} because it was created with a different " f"Python binary."
            )
        else:
            recreate = False

        if recreate:
            shutil.rmtree(path)

    if not path.is_dir():
        logger.info("Creating virtual environment at %s using %s", path, python.path)
        subprocess.check_call([python.path, "-m", "venv", str(path)])
        metadata_file.write_text(databind.json.dumps(python, PythonBinary))

    scripts_dir = path / "Scripts" if os.name == "nt" else path / "bin"
    return CreateVenvResponse(
        python=PythonBinary(
            path=scripts_dir / "python",
            version=python.version,
            md5sum=python.md5sum,
        ),
        scripts_dir=scripts_dir,
    )


##
# PythonVenv Target
##


@dataclass(frozen=True)
class PythonVenv:
    #: The path where the virtual environment should be created.
    path: Path

    #: A constraint for the Python interpreter to use when creating the virtual environment.
    interpreter_constraint: str | None = None


python_venv = make_target_factory("python_venv", None, PythonVenv)


@dataclass(frozen=True)
class PythonVenvInstallGoal(InstallGoal):
    pass


@rule
def make_create_venv_request(venv: PythonVenv) -> CreateVenvRequest:
    return CreateVenvRequest(
        path=venv.path,
        interpreter_constraint=venv.interpreter_constraint,
    )


@rule
def install_python_venv() -> PythonVenvInstallGoal:
    raise NotImplementedError


def register(runner: RuleRunner) -> None:
    runner.engine.add_rules(collect_rules())
    runner.subtypes.register(InstallGoal, PythonVenvInstallGoal)
