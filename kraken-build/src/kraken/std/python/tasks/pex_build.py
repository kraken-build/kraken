import hashlib
import logging
import shlex
import subprocess
import sys
from pathlib import Path

from kraken.core import Property, Task
from kraken.core.system.task import TaskStatus


class PexBuildTask(Task):
    """Build a PEX (Python EXecutable) from a Python requirement spec. Useful to install CLIs from PyPI. The PEX
    will be cached and re-used if the requirements have not changed.

    Important: One of :attr:`console_script` and :attr:`entry_point` is required."""

    binary_name: Property[str]
    requirements: Property[list[str]]
    entry_point: Property[str | None] = Property.default(None)
    console_script: Property[str | None] = Property.default(None)
    interpreter_constraint: Property[str | None] = Property.default(None)
    pex_binary: Property[Path | None] = Property.default(None)
    python: Property[Path | None] = Property.default(None)

    output_file: Property[Path] = Property.output()

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
        return (self.project.context.build_directory / ".store" / hashsum / self.binary_name.get()).with_suffix(".pex")

    def prepare(self) -> TaskStatus | None:
        if not self.entry_point.get() and not self.console_script.get():
            return TaskStatus.failed("One of the `entry_point` or `console_script` properties must be set")
        self.output_file = self._get_output_file_path()
        if self.output_file.get().exists():
            return TaskStatus.skipped(f"PEX {self.binary_name.get()} ({self.output_file.get()}) already exists")
        return TaskStatus.pending()

    def execute(self) -> TaskStatus | None:
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
        return TaskStatus.succeeded(f"PEX {self.binary_name.get()} ({self.output_file.get()}) built successfully")


def _build_pex(
    *,
    output_file: Path,
    requirements: list[str],
    entry_point: str | None = None,
    console_script: str | None = None,
    interpreter_constraint: str | None = None,
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

    (log or logging).info("Building PEX $ %s", " ".join(map(shlex.quote, command)))
    subprocess.run(command, check=True)
