"""Build documentation using [Novella](https://github.com/NiklasRosenstein/novella/)."""

import subprocess
from collections.abc import Sequence
from itertools import chain
from pathlib import Path

from kraken.common import Supplier
from kraken.core import Project, Property, Task, TaskStatus


class NovellaTask(Task):
    """Build or serve documentation with Novella."""

    novella_cmd: Property[Sequence[str]]
    docs_dir: Property[Path | None] = Property.default(None)
    args: Property[Sequence[str]] = Property.default(())

    def execute(self) -> TaskStatus | None:
        command = list(self.novella_cmd.get())
        if self.docs_dir.get():
            command += ["--directory", str(self.docs_dir.get())]
        command += self.args.get()
        return TaskStatus.from_exit_code(command, subprocess.call(command, cwd=self.project.directory))


def novella(
    *,
    project: Project | None = None,
    name: str = "novella",
    novella_version: str,
    additional_requirements: Sequence[str] = (),
    docs_dir: str | Path | None = None,
    build_args: Sequence[str] = (),
    build_task: str | None = None,
    build_group: str | None = None,
    serve_args: Sequence[str] | None = None,
    serve_task: str | None = None,
) -> tuple[NovellaTask, NovellaTask | None]:
    project = project or Project.current()

    novella_cmd = Supplier.of(
        [
            "uv",
            "tool",
            "run",
            "--from",
            f"novella=={novella_version}",
            *chain.from_iterable(("--with", r) for r in additional_requirements),
            "novella",
        ]
    )

    if docs_dir is not None:
        docs_dir = project.directory / docs_dir

    if build_task is None:
        assert name is not None, "need one of build_task/name"
        build_task = name

    _build_task = project.task(build_task, NovellaTask)
    _build_task.novella_cmd = novella_cmd
    _build_task.docs_dir = docs_dir
    _build_task.args = build_args
    if build_group is not None:
        project.group(build_group).add(_build_task)

    if serve_args is not None:
        if serve_task is None:
            assert name is not None, "need one of serve_task/name"
            serve_task = f"{name}.serve"
        _serve_task = project.task(serve_task, NovellaTask)
        _serve_task.novella_cmd = novella_cmd
        _serve_task.docs_dir = docs_dir
        _serve_task.args = serve_args
    else:
        _serve_task = None

    return _build_task, _serve_task
