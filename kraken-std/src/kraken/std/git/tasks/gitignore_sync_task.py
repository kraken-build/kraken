from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from kraken.core.api import Property, Task, TaskStatus
from kraken.core.lib.check_file_contents_task import as_bytes

from ..gitignore import GitignoreException, GitignoreFile
from .const import DEFAULT_GITIGNORE_TOKENS, DEFAULT_KRAKEN_GITIGNORE_OVERRIDES, DEFAULT_KRAKEN_GITIGNORE_PATHS

logger = logging.getLogger(__name__)


class GitignoreSyncTask(Task):
    """This task ensures that a given set of entries are present in a `.gitignore` file. These entries
    are made up of:
        a) :attr`tokens`: Used to source paths from gitignore.io
        b) :attr:`kraken_paths`: Additional required paths added to the generated content
        c) :attr:`kraken_overrides`: Specific entries to be commented out from the generated section
        d) Custom paths added manually by the user directly to the .gitignore

    If :attr:`sort_paths` is enabled, the `.gitignore` file will be sorted (keeping paths grouped under their comments).

    It's common to group this task under the default `fmt` group, as it is similar to formatting a `.gitignore` file.
    """

    sort_paths: Property[bool] = Property.config(default=True)
    sort_groups: Property[bool] = Property.config(default=False)
    tokens: Property[Sequence[str]] = Property.config(default=DEFAULT_GITIGNORE_TOKENS)
    kraken_paths: Property[Sequence[str]] = Property.config(default=DEFAULT_KRAKEN_GITIGNORE_PATHS)
    kraken_overrides: Property[Sequence[str]] = Property.config(default=DEFAULT_KRAKEN_GITIGNORE_OVERRIDES)

    def generate_file_contents(self, file: Path) -> str | bytes:
        gitignore = GitignoreFile([])
        if file.exists():
            try:
                gitignore = GitignoreFile.parse(file)
            except (GitignoreException, ValueError):
                logger.warn("Malformed gitignore detected - generating clean .gitignore")
        gitignore.refresh_generated_content(
            tokens=self.tokens.get(), extra_paths=self.kraken_paths.get(), overrides=self.kraken_overrides.get()
        )
        gitignore.refresh_generated_content_hash()
        gitignore.sort_gitignore(self.sort_paths.get(), self.sort_groups.get())
        return gitignore.render()

    def execute(self) -> TaskStatus:
        file = self.project.directory / ".gitignore"
        try:
            content = self.generate_file_contents(file)
            new_str = as_bytes(content, "utf-8")
            file.write_bytes(new_str)
            return TaskStatus.up_to_date('".gitignore" is up to date')

        except GitignoreException as gitignore_exception:
            return TaskStatus.failed(f"Could not generate to the gitignore file: {gitignore_exception}")
