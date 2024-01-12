import hashlib
import logging
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from pex.pex import PEX  # type: ignore[import]

from kraken.core.system.project import Project
from kraken.core.system.property import Property
from kraken.core.system.task import Task, TaskStatus


class PexBuildTask(Task):
    """Build a PEX (Python EXecutable) from a Python requirement spec. Useful to install CLIs from PyPI. The PEX
    will be cached and re-used if the requirements have not changed."""

    binary_name: Property[str]
    requirements: Property[Sequence[str]]
    entry_point: Property[str | None] = Property.default(None)
    console_script: Property[str | None] = Property.default(None)
    interpreter_constraint: Property[str | None] = Property.default(None)
    pex_binary: Property[Path | None] = Property.default(None)
    python: Property[Path | None] = Property.default(None)

    #: The path to the built PEX file will be written to this property.
    output_file: Property[Path] = Property.output()

    #: A mapping of all console_script entry points to paths of shell scripts that invoke the PEX using the
    #: respective script. These scripts set up the PATH in a way that they can automatically call scripts
    #: from other requirements in the same PEX. You should prefer the console script from this property
    #: instead of setting the :attr:`console_script` attribute and running the :attr:`output_file` directly
    #: if your application requires access to the console scripts provided by its other dependencies in the PEX.
    output_scripts: Property[Mapping[str, Path]] = Property.output()

    #: The directory that contains all `output_scripts`.
    output_scripts_dir: Property[Path] = Property.output()

    def _get_output_file_path(self) -> Path:
        hashsum = hashlib.md5(
            ";".join(
                [
                    self.binary_name.get(),
                    *self.requirements.get(),
                    self.entry_point.get() or "",
                    self.console_script.get() or "",
                    self.interpreter_constraint.get() or "",
                    self.pex_binary.map(str).get() or "",
                    self.python.map(str).get() or "",
                ]
            ).encode()
        ).hexdigest()
        return (
            self.project.context.build_directory
            / ".store"
            / f"{hashsum}-{self.binary_name.get()}"
            / self.binary_name.get()
        ).with_suffix(".pex")

    def prepare(self) -> TaskStatus | None:
        self.output_file = self._get_output_file_path().absolute()
        if self.output_file.get().exists():
            return TaskStatus.skipped(f"PEX `{self.binary_name.get()}` already exists ({self.output_file.get()})")
        return TaskStatus.pending()

    def execute(self) -> TaskStatus | None:
        # After building the PEX, we expose all of it's `console_script` entry points as shell scripts
        # in a separate directory to support when the PEX expects to call a subprocess of one of the
        # console scripts of its own Python dependencies.
        console_scripts_dir = self.output_file.get().parent / "bin"

        try:
            self.output_file.get().parent.mkdir(parents=True, exist_ok=True)
            _build_pex(
                output_file=self.output_file.get(),
                requirements=self.requirements.get(),
                entry_point=self.entry_point.get(),
                console_script=self.console_script.get(),
                interpreter_constraint=self.interpreter_constraint.get(),
                pex_binary=self.pex_binary.get(),
                python=self.python.get(),
            )
        except subprocess.CalledProcessError as exc:
            return TaskStatus.from_exit_code(exc.cmd, exc.returncode)

        # Generate shell scripts that serve as proxies for all the console_script entrypoints in the PEX.
        # We need to update the PATH in the shell script because there's no way I can see to append to the
        # PATH in the built PEX file. Technically there's the --venv mode, but it requires the PEX caller
        # to set `PEX_VENV=true PEX_VENV_BIN_PATH=prepend`.

        console_scripts_files = {}
        console_scripts = _get_console_scripts(PEX(str(self.output_file.get())))
        if console_scripts:
            console_scripts_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info("Exporting %d console_scripts in PEX to %s", len(console_scripts), console_scripts_dir)
            for script in console_scripts:
                file = console_scripts_dir / script
                console_scripts_files[script] = file
                file.write_text(
                    f'#!/bin/sh\nPEX_SCRIPT={script} PATH="{console_scripts_dir.absolute()}:$PATH" '
                    f'"{self.output_file.get().absolute()}" "$@"\n'
                    "exit $?\n"
                )
                file.chmod(0o777)
        else:
            self.logger.info("note: PEX has no console_scripts")

        self.output_scripts_dir = console_scripts_dir
        self.output_scripts = console_scripts_files

        return TaskStatus.succeeded(f"PEX `{self.binary_name.get()}` built successfully ({self.output_file.get()})")


def _build_pex(
    *,
    output_file: Path,
    requirements: Sequence[str],
    entry_point: str | None = None,
    console_script: str | None = None,
    interpreter_constraint: str | None = None,
    inject_env: Mapping[str, str] | None = None,
    venv: bool = False,
    pex_binary: Path | None = None,
    python: Path | None = None,
    log: logging.Logger | None = None,
) -> None:
    """Invokes the `pex` CLI to build a PEX file and write it to :param:`output_file`.

    :param requirements: The Python package requirements for the packages to include in the PEX.
    :param output_file: The path to write the PEX to.
    :param entry_point: A Python entry point (e.g. in the form `module:member`) to run.
    :param console_script: The name of the `console_script` entry point to use as the entry point for the PEX.
    :param interpreter_constraint: Restrict the Python version that will be used to execute the PEX.
    :param pex_binary: Path to the `pex` binary to execute. If not specified, `python -m pex` will be used
        taking into account the :param:`python` parameter.
    :param python: The Python executable to run `python -m pex` with. If not set, defaults to :data:`sys.executable`.
    """

    if pex_binary is not None:
        command = [str(pex_binary)]
    else:
        command = [
            str(python or sys.executable),
            "-m",
            "pex",
            "-v",
        ]

    command += [
        "--output-file",
        str(output_file),
        *requirements,
    ]
    if entry_point is not None:
        command += ["--entry-point", entry_point]
    if console_script is not None:
        command += ["--console-script", console_script]
    if interpreter_constraint is not None:
        command += ["--interpreter-constraint", interpreter_constraint]
    for key, value in (inject_env or {}).items():
        command += ["--inject-env", f"{key}={value}"]
    if venv:
        command += ["--venv"]

    (log or logging).info("Building PEX $ %s", " ".join(map(shlex.quote, command)))
    subprocess.run(command, check=True)


def _get_console_scripts(pex: PEX) -> set[str]:
    """Return all entry points registered under `console_script` for this PEX."""

    result = set()
    for dist in pex.resolve():
        result.update(dist.get_entry_map().get("console_scripts", {}).keys())
    return result


def pex_build(
    binary_name: str | None = None,
    *,
    requirements: Sequence[str],
    entry_point: str | None = None,
    console_script: str | None = None,
    task_name: str | None = None,
    project: Project | None = None,
) -> PexBuildTask:
    assert binary_name or console_script, "binary_name or console_script must be set"
    binary_name = binary_name or console_script

    task = (project or Project.current()).task(task_name or f"pexBuild.{binary_name}", PexBuildTask)
    task.binary_name = binary_name
    task.requirements = requirements
    task.entry_point = entry_point
    task.console_script = console_script
    return task
