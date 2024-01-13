import logging
import os
import subprocess
import sys
import textwrap

from more_itertools import flatten

from kraken.build.experimental.common.targets import Executable
from kraken.build.experimental.rules import rule, get, resolve_dependencies, InstallGoal, BuildGoal
from kraken.build.experimental.python.targets import (
    PythonApp,
    PexRequest,
    PexResult,
    PythonPex,
    PythonRequirements,
    PythonRuntime,
    PythonRuntimeRequest,
    PythonSources,
    VenvRequest,
    VenvResult,
)
from kraken.core.system.project import Project
from kraken.std.python.pyproject import PyprojectHandler

logger = logging.getLogger(__name__)

# TODO: Hash function definition into rule inputs in adjudicator module (as to rebuild when the implementation#
#       changes instead of reusing the cache).


##
# PythonApp
##


@rule()
def python_app_infer_sources(target: PythonApp) -> PythonSources:
    """Infer the source files from the project's `pyproject.toml`."""

    project = target.project

    sources = []
    for directory in map(lambda d: project.directory / d, [target.source_directory, target.tests_directory]):
        if not directory.exists():
            continue
        sources.extend([str(file.relative_to(project.directory)) for file in directory.rglob("*.py")])

    return PythonSources(project=project, files=tuple(sources))


@rule()
def python_app_infer_python_requirements(target: PythonApp) -> PythonRequirements:
    """Infer a list of Python requirements from a requirements file, `pyproject.toml` or tool-specific lock file and
    create a static target that represents them. The following tool-specific `pyproject.toml` formats and lock files
    are supported and will be automatically detected:

    * Setuptools
    * Flit
    * Poetry
    * PDM

    :param name: The name of the target.
    :param requirements_file: The path to the requirements file. If not specified, but the file exists, it will be used.
    :param lock_file: The path to the tool-specific lock file. If not specified, but the file exists, it will be used,
        unless a requirements file takes precedence.
    :param pyproject_toml: The path to the `pyproject.toml` file. If not specified, but the file exists, it will be
        used (unless a requirements file or lock file takes precedence).
    """

    # TODO: Support requirement groups (e.g. `requirements.txt` and `requirements-dev.txt`).

    project = target.project
    requirements_file = target.requirements_file
    lock_file = target.lock_file
    pyproject_toml = target.pyproject_toml

    if requirements_file is None and lock_file is None and pyproject_toml is None:
        if os.path.isfile(file := str(project.directory / "requirements.txt")):
            requirements_file = file
        # elif os.path.isfile(file := str(project.directory / "poetry.lock")):
        #     lock_file = file
        # elif os.path.isfile(file := str(project.directory / "pdm.lock")):
        #     lock_file = file
        elif os.path.isfile(file := str(project.directory / "pyproject.toml")):
            pyproject_toml = file

    if requirements_file is None and lock_file is None and pyproject_toml is None:
        raise ValueError(f"Missing requirements.txt/poetry.lock/pdm.lock/pyproject.toml file in {project.directory}.")

    requirements: list[str] | None = None

    if pyproject_toml is not None:
        # TODO: Read `[project].requirements` or `[tool.poetry.dependencies]`.
        requirements = []
        logger.warning("Parsing of pyproject.toml files is not yet implemented, coming up with empty requirements")

    if lock_file is not None:
        # TODO: Use `poetry export` or `pdm export` to generate a `requirements.txt` file.
        raise NotImplementedError(f"Parsing of lock files ({lock_file}) is not yet implemented.")

    if requirements_file is not None:
        with open(requirements_file) as fp:
            requirements = [line.strip() for line in fp.readlines() if line.strip() and not line.startswith("#")]

    assert requirements is not None, "Requirements could not be inferred."

    return PythonRequirements(requirements=tuple(requirements))


@rule()
def python_app_to_run_request(app: PythonApp) -> Executable:
    """ Run a Python app within its virtual env. """

    venv = get(VenvResult, app)

    module, member = app.entry_point.split(":")
    code = textwrap.dedent(fr'''
        import re
        import sys
        from {module} import {member}
        if __name__ == '__main__':
            sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
            sys.exit({member}())
    ''')

    return Executable(path=venv.python_bin, argv=("-c", code))


@rule()
def python_app_to_venv_request(target: PythonApp) -> VenvRequest:

    # If no interpreter constraint is specified, try to find it from the project's metadata.
    if target.interpreter_constraint is None:
        handler = get(PyprojectHandler, target.project)
        interpreter_constraint = handler.get_python_version_constraint()
        logger.info("Using interpreter constraint from pyproject: %s", interpreter_constraint)
    else:
        interpreter_constraint = target.interpreter_constraint

    return VenvRequest(
        project=target.project,
        requirements=get(PythonRequirements, target).requirements,
        interpreter_constraint=interpreter_constraint,
    )


@rule()
def python_app_to_pyproject_handler(project: Project) -> PyprojectHandler:
    from kraken.std.python.buildsystem import detect_build_system
    from kraken.std.python.pyproject import Pyproject

    file = project.directory / "pyproject.toml"
    if not file.exists():
        raise RuntimeError(f"Could not find pyproject.toml file for project {project}.")

    pyproject = Pyproject.read(file)
    build_system = detect_build_system(project.directory)
    if not build_system:
        raise RuntimeError(f"Could not determine build system for project {project}.")

    return build_system.get_pyproject_reader(pyproject)

##
# PythonPex
##


@rule()
def python_pex_to_pex_request(target: PythonPex) -> PexRequest:
    requirements = resolve_dependencies(
        target.project,
        dependencies=target.dependencies,
        target_type=PythonRequirements,
    )

    # If no interpreter constraint is specified, try to find it from the project's metadata.
    if target.interpreter_constraint is None:
        handler = get(PyprojectHandler, target.project)
        interpreter_constraint = handler.get_python_version_constraint()
        logger.info("Using interpreter constraint from pyproject: %s", interpreter_constraint)
    else:
        interpreter_constraint = target.interpreter_constraint

    return PexRequest(
        project=target.project,
        requirements=tuple(flatten(req.requirements for req in requirements)),
        entry_point=target.entry_point,
        binary_out=target.project.build_directory / "dist" / f"{target.name}.pex",
        interpreter_constraint=interpreter_constraint,
    )


##
# PythonRuntime
##


@rule()
def python_runtime_request(request: PythonRuntimeRequest) -> PythonRuntime:
    from kraken.common.findpython import (
        get_candidates,
        evaluate_candidates,
        InterpreterVersionCache,
        match_version_constraint,
    )

    logger.info("Evaluating Python runtime candidates for interpreter_constraint=%s", request.interpreter_constraint)

    candidates = evaluate_candidates(get_candidates(), InterpreterVersionCache())
    if not candidates:
        raise RuntimeError("No Python interpreters found.")

    if request.interpreter_constraint is None:
        logger.debug("No interpreter constraint specified, using first (%s).", candidates[0])
        selected = candidates[0]
    else:
        candidates = [c for c in candidates if match_version_constraint(request.interpreter_constraint, c["version"])]
        if not candidates:
            raise RuntimeError(f"No Python interpreters found matching constraint: {request.interpreter_constraint}")

        logger.debug("Found %d interpreters matching constraint: %s", len(candidates), request.interpreter_constraint)
        logger.debug("Using first interpreter: %s", candidates[0])
        selected = candidates[0]

    return PythonRuntime(path=selected["path"], version=selected["version"])


##
# VenvRequest
##


@rule()
def venv_request_install(request: VenvRequest) -> VenvResult:
    """Install a virtual environment."""

    # TODO: Support installing via Poetry/PDM if the project is using that.

    # TODO: Allow customizing the installation via CLI arguments, e.g. to select given extras, a particular
    #       interpretered, install into a secondary environment (ultimately allowing the user to install two
    #       separate environments for the same project).

    runtime = get(PythonRuntime, PythonRuntimeRequest(interpreter_constraint=request.interpreter_constraint))

    venv_dir = request.project.directory / ".venv"

    # TODO: Add option for fresh install.
    if not venv_dir.exists():
        logger.info("Create virtual environment: %s", venv_dir)
        command = [runtime.path, "-m", "venv", str(venv_dir)]
        if request.upgrade_deps:
            command.extend(["--upgrade-deps"])
        if request.system_site_packages:
            command.extend(["--system-site-packages"])

        subprocess.run(command, check=True)
    else:
        logger.info("Virtual environment already exists: %s", venv_dir)

    # TODO: Hash requirements to determine if reinstall is necessary.
    # TODO: Add option to pass --upgrade flag to Pip.

    logger.info("Installing requirements into virtual environment: %s", venv_dir)
    python_bin = venv_dir / "bin" / "python"
    command = [str(python_bin), "-m", "pip", "install", *request.requirements, "-e", str(request.project.directory)]
    subprocess.run(command, check=True)

    return VenvResult(python_bin=python_bin)


@rule()
def venv_result_is_install_goal(_: VenvResult) -> InstallGoal:
    """Allows the VENV to be installed via the #InstallGoal."""

    return InstallGoal()


##
# PexRequest
##


@rule()
def python_pex_build(request: PexRequest) -> PexResult:
    # TODO: Build an entire PexRequest object and generate the PEX from that to support caching.

    command = [
        sys.executable,
        "-m",
        "pex",
        "--output-file",
        str(request.binary_out.absolute()),
        "--entry-point",
        request.entry_point,
        *request.requirements,
        str(request.project.directory),
    ]

    if request.interpreter_constraint is not None:
        command.extend(["--interpreter-constraint", request.interpreter_constraint])

    print("Building PEX:", command)
    subprocess.run(command, check=True)

    return PexResult(binary_out=request.binary_out)


@rule()
def pex_result_is_build_goal(_: PexResult) -> BuildGoal:
    """Allows the PEX to be built via the #BuildGoal."""

    return BuildGoal()


@rule()
def pex_result_is_executable(result: PexResult) -> Executable:
    """Allows the PEX to be executed via the #RunGoal."""

    return Executable(path=result.binary_out)
