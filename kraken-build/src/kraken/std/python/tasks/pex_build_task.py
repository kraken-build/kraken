import hashlib
import logging
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from kraken.core.system.project import Project
from kraken.core.system.property import Property
from kraken.core.system.task import Task, TaskStatus
from kraken.std.util.url import inject_url_credentials, redact_url_password

logger = logging.getLogger(__name__)
default_index_url: str | None = None


class PexBuildTask(Task):
    """Build a PEX (Python EXecutable) from a Python requirement spec. Useful to install CLIs from PyPI. The PEX
    will be cached and re-used if the requirements have not changed."""

    binary_name: Property[str]
    requirements: Property[Sequence[str]]
    entry_point: Property[str | None] = Property.default(None)
    console_script: Property[str | None] = Property.default(None)
    interpreter_constraint: Property[str | None] = Property.default(None)
    venv: Property[Literal["prepend", "append"] | None] = Property.default(None)
    pex_binary: Property[Path | None] = Property.default(None)
    python: Property[Path | None] = Property.default(None)
    index_url: Property[str | None] = Property.default(None)

    #: The path to the built PEX file will be written to this property.
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
                    self.venv.get() or "",
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
        try:
            self.output_file.get().parent.mkdir(parents=True, exist_ok=True)
            _build_pex(
                output_file=self.output_file.get(),
                requirements=self.requirements.get(),
                entry_point=self.entry_point.get(),
                console_script=self.console_script.get(),
                interpreter_constraint=self.interpreter_constraint.get(),
                venv=self.venv.get(),
                pex_binary=self.pex_binary.get(),
                python=self.python.get(),
                index_url=self.index_url.get() or _get_default_index_url(self.project),
            )
        except subprocess.CalledProcessError as exc:
            return TaskStatus.from_exit_code(exc.cmd, exc.returncode)

        return TaskStatus.succeeded(f"PEX `{self.binary_name.get()}` built successfully ({self.output_file.get()})")


def _build_pex(
    *,
    output_file: Path,
    requirements: Sequence[str],
    entry_point: str | None = None,
    console_script: str | None = None,
    interpreter_constraint: str | None = None,
    venv: Literal["prepend", "append"] | None = None,
    inject_env: Mapping[str, str] | None = None,
    pex_binary: Path | None = None,
    python: Path | None = None,
    index_url: str | None = None,
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
        command = [str(python or sys.executable), "-m", "pex", "-v"]

    command += [
        "--pip-version",
        "latest",
        "--resolver-version",
        "pip-2020-resolver",
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
    if venv is not None:
        command += ["--venv", venv]
    for key, value in (inject_env or {}).items():
        command += ["--inject-env", f"{key}={value}"]

    safe_command = list(command)
    if index_url is not None:
        command += ["--index-url", index_url]
        safe_command += ["--index-url", redact_url_password(index_url)]

    (log or logging).info("Building PEX $ %s", " ".join(map(shlex.quote, safe_command)))
    subprocess.run(command, check=True)


def pex_build(
    binary_name: str | None = None,
    *,
    requirements: Sequence[str],
    entry_point: str | None = None,
    console_script: str | None = None,
    interpreter_constraint: str | None = None,
    venv: Literal["prepend", "append"] | None = None,
    index_url: str | None = None,
    task_name: str | None = None,
    project: Project | None = None,
) -> PexBuildTask:
    assert binary_name or console_script, "binary_name or console_script must be set"
    binary_name = binary_name or console_script
    project = project or Project.current()
    task_name = task_name or f"pexBuild.{binary_name}"

    existing_task = project.tasks().get(task_name, None)
    if (
        isinstance(existing_task, PexBuildTask)
        and existing_task.binary_name.get() == binary_name
        and existing_task.requirements.get() == requirements
        and existing_task.entry_point.get() == entry_point
        and existing_task.console_script.get() == console_script
        and existing_task.interpreter_constraint.get() == interpreter_constraint
        and existing_task.venv.get() == venv
        and existing_task.index_url.get() == index_url
    ):
        return existing_task

    task = project.task(task_name, PexBuildTask)
    task.binary_name = binary_name
    task.requirements = requirements
    task.entry_point = entry_point
    task.console_script = console_script
    task.interpreter_constraint = interpreter_constraint
    task.venv = venv
    task.index_url = index_url
    return task


def pex_set_default_index_url(url: str) -> None:
    """Set the default index URL for Pex globally."""

    global default_index_url
    default_index_url = url


def _get_default_index_url(project: Project | None) -> str | None:
    """Looks up the default Python package index in the Python settings of the current project, or falls back
    to the global `default_index_url`."""

    from kraken.std.python.settings import python_settings

    settings = python_settings(project=project)
    if (idx := settings.get_primary_index()) is None:
        return default_index_url
    if idx.credentials:
        return inject_url_credentials(idx.index_url, *idx.credentials)
    return idx.index_url
