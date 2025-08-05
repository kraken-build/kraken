"""Build documentation using [MkDocs](https://www.mkdocs.org/)."""

import os
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Annotated, Literal

from cyclopts import Parameter

from kraken.common import Supplier
from kraken.core import Project, Property, Task, TaskStatus
from kraken.core.system.aspect import RunAspect, parse_options


@dataclass
class MkDocsRunOptions:
    """
    Parameters
    ----------
    serve:
        Serve the docs locally instead of building them.
    address:
        The address to listen to when `--serve` is specified.
    clean:
        Build the site without any effects of `mkdocs serve` - pure `mkdocs build`, then serve.
    livereload:
        Use live reloading of the development server.
    strict:
        Use strict mode. Overrides what's defined on the task-level.
    """

    serve: bool = False
    address: Annotated[str, Parameter(env_var="MKDOCS_PORT")] = "localhost:8000"
    clean: bool = False
    livereload: bool = True
    strict: bool | None = None


class MkDocsTask(Task, RunAspect.Implements):
    """
    Build docs with MkDocs.

    See [MkDocsRunOptions] for parameters you can pass via `kraken run invoke`.
    """

    mkdocs_cmd: Property[Sequence[str]] = Property.default(["mkdocs"])
    mkdocs_root: Property[Path | None] = Property.default(None)
    args: Property[Sequence[str]] = Property.default(())
    strict: Property[bool] = Property.default(True)
    build_directory: Property[Path]
    watch_files: Property[Sequence[Path]] = Property.default(())

    def execute(self) -> TaskStatus | None:
        strict = self.strict.get()
        build_directory = self.build_directory.get_or_else(
            lambda: (self.project.build_directory / self.name / "_site").absolute()
        )
        watch_files = self.watch_files.get()
        args = list(self.args.get())

        mode: Literal["build", "serve"] = "build"
        if run := RunAspect.current_options(self):
            opts = parse_options(run.args, MkDocsRunOptions)
            if opts.serve:
                mode = "serve"
                args += ["-a", opts.address]
                if not opts.livereload:
                    args += ["--no-livereload"]

            if opts.clean:
                args += ["--clean"]
            if opts.strict is not None:
                strict = opts.strict

        # Build up the Mkdocs command to invoke.

        command = [*self.mkdocs_cmd.get(), "serve" if mode == "serve" else "build", *args]
        if mode != "serve":
            command += ["-d", os.fspath(build_directory)]
        if strict:
            command += ["--strict"]
        if mode == "serve":
            for path in watch_files:
                command += ["-w", os.fspath(path)]

        if mkdocs_root := self.mkdocs_root.get():
            cwd = self.project.directory / mkdocs_root
        else:
            cwd = self.project.directory

        self.logger.info("$ %s", shlex.join(command))
        return TaskStatus.from_exit_code(command, subprocess.call(command, cwd=cwd))


def mkdocs(
    *,
    requirements: Sequence[str] = ("mkdocs>=1.5.3,<2.0.0"),
    mkdocs_root: Path | str | None = None,
    watch_files: Sequence[Path | str] = (),
    task_prefix: str = "mkdocs",
    project: Project | None = None,
    strict: bool = True,
) -> MkDocsTask:
    project = project or Project.current()

    mkdocs_cmd = Supplier.of(["uv", "tool", "run", *chain.from_iterable(("--with", r) for r in requirements), "mkdocs"])
    final_watch_files = [(project.directory / x).absolute() for x in watch_files]

    build_task = project.task(f"{task_prefix}", MkDocsTask)
    build_task.mkdocs_root = project.directory / (mkdocs_root or "")
    build_task.mkdocs_cmd = mkdocs_cmd
    build_task.watch_files = final_watch_files
    build_task.strict = strict

    return build_task
