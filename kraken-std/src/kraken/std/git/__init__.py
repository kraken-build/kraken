""" Tools for Git versioned projects. """

from __future__ import annotations

from typing import Optional, Sequence, cast

from kraken.core.api import Project

from .tasks.const import (
    DEFAULT_GITIGNORE_TOKENS,
    DEFAULT_KRAKEN_GITIGNORE_OVERRIDES,
    DEFAULT_KRAKEN_GITIGNORE_PATHS,
    GITIGNORE_TASK_NAME,
)
from .tasks.gitignore_check_task import GitignoreCheckTask
from .tasks.gitignore_sync_task import GitignoreSyncTask
from .version import GitVersion, git_describe

__all__ = [
    "git_describe",
    "GitVersion",
    "GitignoreSyncTask",
    "GitignoreCheckTask",
    "gitignore",
    "GITIGNORE_TASK_NAME",
    "DEFAULT_GITIGNORE_TOKENS",
    "DEFAULT_KRAKEN_GITIGNORE_PATHS",
    "DEFAULT_KRAKEN_GITIGNORE_OVERRIDES",
]


def gitignore(
    tokens: Sequence[str] = DEFAULT_GITIGNORE_TOKENS,
    kraken_paths: Sequence[str] = DEFAULT_KRAKEN_GITIGNORE_PATHS,
    kraken_overrides: Sequence[str] = DEFAULT_KRAKEN_GITIGNORE_OVERRIDES,
    project: Project | None = None,
) -> GitignoreSyncTask:
    project = project or Project.current()
    task = cast(Optional[GitignoreSyncTask], project.tasks().get(GITIGNORE_TASK_NAME))
    if task is None:
        task = project.do(
            GITIGNORE_TASK_NAME,
            GitignoreSyncTask,
            group="apply",
            tokens=tokens,
            kraken_paths=kraken_paths,
            kraken_overrides=kraken_overrides,
        )
        project.do(
            f"{GITIGNORE_TASK_NAME}.check",
            GitignoreCheckTask,
            group="check",
            tokens=tokens,
            kraken_paths=kraken_paths,
            kraken_overrides=kraken_overrides,
        )
    else:
        raise ValueError("cannot add gitignore task: task can only be added once")
    return task
