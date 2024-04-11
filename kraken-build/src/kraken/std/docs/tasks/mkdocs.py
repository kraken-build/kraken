""" Build documentation using [MkDocs](https://www.mkdocs.org/). """

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

from kraken.core import Project, Property, Task, TaskStatus
from kraken.std.python.tasks.pex_build_task import pex_build


class MkDocsTask(Task):
    """Build docs with MkDocs."""

    mkdocs_bin: Property[str] = Property.default("mkdocs")
    mkdocs_root: Property[Path | None] = Property.default(None)
    args: Property[Sequence[str]] = Property.default(())

    def execute(self) -> TaskStatus | None:
        command = [self.mkdocs_bin.get(), *self.args.get()]
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

    mkdocs_bin = pex_build(
        console_script="mkdocs",
        requirements=requirements,
        project=project,
        venv="prepend",
    ).output_file.map(str)

    build_dir = (project.build_directory / task_prefix / "_site").absolute()

    build_task = project.task(f"{task_prefix}.build", MkDocsTask)
    build_task.mkdocs_root = project.directory / (mkdocs_root or "")
    build_task.mkdocs_bin = mkdocs_bin
    build_task.args = ["build", "-d", str(build_dir), "--strict"]

    port = int(os.environ.get("MKDOCS_PORT", "8000"))
    watch_files = [(project.directory / x).absolute() for x in watch_files]

    serve_task = project.task(f"{task_prefix}.serve", MkDocsTask)
    build_task.mkdocs_root = project.directory / (mkdocs_root or "")
    serve_task.mkdocs_bin = mkdocs_bin
    serve_args = ["serve", "-a", f"localhost:{port}"]
    for w in watch_files:
        serve_args += ["-w", str(w)]
    serve_task.args = serve_args

    return build_task, serve_task
