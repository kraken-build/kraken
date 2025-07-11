"""Build documentation using [MkDocs](https://www.mkdocs.org/)."""

import os
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
from kraken.core.system.task import VoidTask


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
    """

    serve: bool = False
    address: Annotated[str, Parameter(env_var="MKDOCS_PORT")] = "localhost:8000"
    clean: bool = False
    livereload: bool = True


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

    _do_not_use_other_task_name: Property[str]
    _do_not_use_mode: Property[Literal["build", "serve"]] = Property.default("build")
    """
    For backwards compatibility, the task can be put into "serve" mode to always run "mkdocs serve". This
    is deprecated since v0.46.0 and will be removed in a future version. Use `kraken invoke :mkdocs --serve`
    instead (assuming `:mkdocs` is your [MkDocsTask]).
    """

    def execute(self) -> TaskStatus | None:
        mode = self._do_not_use_mode.get()
        strict = self.strict.get()
        build_directory = self.build_directory.get_or_else(
            lambda: (self.project.build_directory / self.name / "_site").absolute()
        )
        watch_files = self.watch_files.get()
        args = list(self.args.get())

        if mode == "serve":
            other = self._do_not_use_other_task_name.get_or("mkdocs")
            self.logger.warning(
                "Using `MkDocsTask.mode == 'serve'` is deprecated and will be removed in a future version. You "
                f"should use `kraken invoke {other} --serve` instead.."
            )

            port = int(os.environ.get("MKDOCS_PORT", "8000"))
            args += ["-a", f"localhost:{port}"]

        if run := RunAspect.current_options():
            opts = parse_options(run.args, MkDocsRunOptions)
            if opts.serve:
                mode = "serve"
                args += ["-a", opts.address]
                if opts.clean:
                    args += ["--clean"]
                if not opts.livereload:
                    args += ["--no-livereload"]

        # Build up the Mkdocs command to invoke.

        command = [*self.mkdocs_cmd.get(), "serve" if mode == "serve" else "build", *args]
        if mode != "serve":
            command += ["-d", os.fspath(build_directory)]
        if strict:
            command += ["--strict"]
        for path in watch_files:
            command += ["-w", os.fspath(path)]

        if mkdocs_root := self.mkdocs_root.get():
            cwd = self.project.directory / mkdocs_root
        else:
            cwd = self.project.directory

        self.logger.info("$ %s", command)
        return TaskStatus.from_exit_code(command, subprocess.call(command, cwd=cwd))


def mkdocs(
    *,
    requirements: Sequence[str] = ("mkdocs>=1.5.3,<2.0.0"),
    mkdocs_root: Path | str | None = None,
    watch_files: Sequence[Path | str] = (),
    task_prefix: str = "mkdocs",
    project: Project | None = None,
) -> tuple[MkDocsTask, MkDocsTask]:
    project = project or Project.current()

    mkdocs_cmd = Supplier.of(["uv", "tool", "run", *chain.from_iterable(("--with", r) for r in requirements), "mkdocs"])

    build_task = project.task(f"{task_prefix}", MkDocsTask)
    build_task.mkdocs_root = project.directory / (mkdocs_root or "")
    build_task.mkdocs_cmd = mkdocs_cmd

    # The .build and .serve variants are deprecated and here only for backwards compatibility. Use
    # `krakenw invoke :{task_prefix} [--serve]` instead.

    build_alias_task = project.task(f"{task_prefix}.build", VoidTask)
    build_alias_task.message = f"The `{task_prefix}.build` is deprecated, run `{task_prefix}` directly"
    build_alias_task.depends_on(build_task)

    serve_task = project.task(f"{task_prefix}.serve", MkDocsTask)
    serve_task.mkdocs_root = project.directory / (mkdocs_root or "")
    serve_task.mkdocs_cmd = mkdocs_cmd
    serve_task._do_not_use_mode = "serve"
    serve_task._do_not_use_other_task_name = str(build_task.address)
    serve_task.watch_files = [(project.directory / x).absolute() for x in watch_files]

    return build_task, serve_task
