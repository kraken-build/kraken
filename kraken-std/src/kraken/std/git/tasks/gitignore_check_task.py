from __future__ import annotations

from pathlib import Path
from typing import Sequence

from kraken.common.path import try_relative_to
from kraken.core.api import Project, Property, Task, TaskStatus
from termcolor import colored

from ..gitignore import GitignoreException, GitignoreFile
from .const import (
    DEFAULT_GITIGNORE_TOKENS,
    DEFAULT_KRAKEN_GITIGNORE_OVERRIDES,
    DEFAULT_KRAKEN_GITIGNORE_PATHS,
    GITIGNORE_TASK_NAME,
)


def as_bytes(v: str | bytes, encoding: str) -> bytes:
    return v.encode(encoding) if isinstance(v, str) else v


class GitignoreCheckTask(Task):
    """This task checks that a given set of entries are present in a `.gitignore` file. This has the
    same params as :class:`GitignoreSyncTask`
    """

    file: Property[Path]
    sort_paths: Property[bool] = Property.config(default=True)
    sort_groups: Property[bool] = Property.config(default=False)
    tokens: Property[Sequence[str]] = Property.config(default=DEFAULT_GITIGNORE_TOKENS)
    kraken_paths: Property[Sequence[str]] = Property.config(default=DEFAULT_KRAKEN_GITIGNORE_PATHS)
    kraken_overrides: Property[Sequence[str]] = Property.config(default=DEFAULT_KRAKEN_GITIGNORE_OVERRIDES)

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.file.setcallable(lambda: self.project.directory / ".gitignore")

    def execute(self) -> TaskStatus:
        file = try_relative_to(self.file.get())
        file_fmt = colored(str(file), "yellow", attrs=["bold"])

        uptask = colored(GITIGNORE_TASK_NAME, "blue", attrs=["bold"])
        message_suffix = f", run {uptask} to generate it"

        if not file.exists():
            return TaskStatus.failed(f'file "{file_fmt}" does not exist{message_suffix}')
        if not file.is_file():
            return TaskStatus.failed(f'"{file}" is not a file')
        try:
            gitignore = GitignoreFile.parse(file)
            if not gitignore.check_generated_content_hash():
                return TaskStatus.failed(f'generated section of file "{file_fmt}" was modified{message_suffix}')
            if not gitignore.check_generation_parameters(
                tokens=self.tokens.get(), extra_paths=self.kraken_paths.get(), overrides=self.kraken_overrides.get()
            ):
                return TaskStatus.failed(f'file "{file_fmt}" is not up to date, call `kraken run apply` to fix')

            unsorted = gitignore.render()

            gitignore.sort_gitignore(self.sort_paths.get(), self.sort_groups.get())
            sorted = gitignore.render()

            if unsorted != sorted:
                return TaskStatus.failed(f'"{file_fmt}" is not sorted{message_suffix}')

            return TaskStatus.up_to_date(f'file "{file_fmt}" is up to date')
        except GitignoreException as gitignore_exception:
            return TaskStatus.failed(f"{gitignore_exception}{message_suffix}")
