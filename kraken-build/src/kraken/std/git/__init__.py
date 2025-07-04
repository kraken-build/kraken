"""Tools for Git versioned projects."""

from __future__ import annotations

import warnings
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
    "gitignore_extend",
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

    # DEPRECATE: We want to get rid of gitignore.io tokens feature.
    if gitignore_io_tokens:
        warnings.warn(
            "gitignore(gitignore_io_tokens) is deprecated and will be removed in a future version", DeprecationWarning
        )
    if gitignore_io_allow_http_request_backfill:
        warnings.warn(
            "gitignore(gitignore_io_allow_http_request_backfill) is deprecated and will be removed in a future version",
            DeprecationWarning,
        )

    project = project or Project.current()
    task = project.task(name, tasks.GitignoreSyncTask, group=group)
    task.file.set(Path(gitignore_file))
    if generated_content is not None:
        task.generated_content.setmap(lambda x: [*x, *generated_content])
    task.gitignore_io_tokens.set(list(gitignore_io_tokens))
    task.gitignore_io_allow_http_request_backfill.set(gitignore_io_allow_http_request_backfill)
    task.where.set(where)
    return task, task.create_check(group=check_group)


def gitignore_extend(
    *,
    project: Project | None = None,
    patterns: Sequence[str],
    dedup: bool = True,
) -> None:
    """
    Extend the Gitignore task's generated content section by the given *pattern*s.

    Args:
        project: The project to look for the Gitignore task configuration in. If it is not specified, it will be
                 searched in the currently active project and any of its parents (often the Gitignore tasks only exist
                 on the root project).
        patterns: The patterns to add to the config.
        dedup: If enabled, do not add any patterns that are already present.
    """

    if project is None:
        projects = []
        project = Project.current()
        while project:
            projects.append(project)
            project = project.parent

    else:
        projects = [project]

    task: tasks.GitignoreSyncTask | None
    for project in projects:
        task = next((t for t in project.tasks().values() if isinstance(t, tasks.GitignoreSyncTask)), None)
        if task is not None:
            break

    if task is None:
        raise ValueError("Could not find GitignoreSyncTask")

    task.generated_content.setmap(lambda x: [*x, *(p for p in patterns if p not in x)] if dedup else [*x, *patterns])
