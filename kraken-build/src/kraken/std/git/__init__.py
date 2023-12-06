""" Tools for Git versioned projects. """

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from kraken.core import Project
from kraken.std.util.check_file_contents_task import CheckFileContentsTask

from . import tasks
from .config import dump_gitconfig, load_gitconfig
from .version import GitVersion, git_describe

__all__ = [
    "tasks",
    "load_gitconfig",
    "dump_gitconfig",
    "git_describe",
    "GitVersion",
    "gitignore",
]


def gitignore(
    *,
    name: str = "gitignore",
    group: str = "apply",
    check_group: str = "check",
    gitignore_file: str | Path = ".gitignore",
    generated_content: Sequence[str] | None = (),
    gitignore_io_tokens: Sequence[str] = (),
    gitignore_io_allow_http_request_backfill: bool = False,
    where: Literal["top", "bottom"] = "top",
    project: Project | None = None,
) -> tuple[tasks.GitignoreSyncTask, CheckFileContentsTask]:
    """
    Creates a #GitignoreSyncTask and #CheckFileContentsTask for the given project.
    """

    project = project or Project.current()
    task = project.task(name, tasks.GitignoreSyncTask, group=group)
    task.file.set(Path(gitignore_file))
    if generated_content is not None:
        task.generated_content.setmap(lambda x: [*x, *generated_content])
    task.gitignore_io_tokens.set(list(gitignore_io_tokens))
    task.gitignore_io_allow_http_request_backfill.set(gitignore_io_allow_http_request_backfill)
    task.where.set(where)
    return task, task.create_check(group=check_group)
