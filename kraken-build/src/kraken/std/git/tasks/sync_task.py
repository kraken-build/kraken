from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from kraken.core import Project, Property
from kraken.std.git.gitignore.generated import join_generated_section, split_generated_section
from kraken.std.util.render_file_task import RenderFileTask

from ..gitignore.gitignore_io import gitignore_io_fetch_cached
from ..gitignore.parser import GitignoreEntry, GitignoreFile

logger = logging.getLogger(__name__)


class GitignoreSyncTask(RenderFileTask):
    """
    This task ensures that a `.gitignore` file contains the generated content that it is expected to contain,
    in addition to preserving any user-defined content.
    """

    #: The generated content that the `.gitignore` file is expected to contain. This content will be
    #: enclosed in markers that indicate the start and end of the generated section.
    generated_content: Property[list[str]] = Property.default_factory(
        lambda: [
            "# Kraken",
            "/build",
        ]
    )

    #: Specify a list of gitignore.io tokens to include in addition to #generated_content. These tokens
    #: will be placed before the values from #generated_content.
    gitignore_io_tokens: Property[list[str]] = Property.default_factory(list)

    #: Whether to permit backfilling gitignore.io tokens that are not distributed with kraken-std via
    #: and HTTP request to gitignore.io.
    gitignore_io_allow_http_request_backfill: Property[bool] = Property.default(False)

    #: Where to place the generated content, if no generated content is found in the file.
    where: Property[Literal["top", "bottom"]] = Property.default("top")

    def get_file_contents(self, file: Path) -> str:
        if file.exists():
            # Read the existing content, so we can replace the generated section.
            user1, generated, user2 = split_generated_section(GitignoreFile.parse(file))
        else:
            user1, generated, user2 = GitignoreFile(), GitignoreFile(), GitignoreFile()

        # When no generated section is found, the entire file content sits in user1. If we want our new generated
        # content to sit at the top, we need to swap user1 and user2.
        if not generated and self.where.get() == "top":
            user1, user2 = user2, user1

        # Replace the generated content.
        generated = GitignoreFile()
        if tokens := self.gitignore_io_tokens.get():
            generated += GitignoreFile.parse(
                gitignore_io_fetch_cached(tokens, backfill=self.gitignore_io_allow_http_request_backfill.get())
            )
        # User-provided generated content, allowing for overrides to API-generated content.
        generated += GitignoreFile.parse(self.generated_content.get())

        # Ensure there's at least one blank space between sections.
        if user1 and generated and (user1[-1] != "" and generated[0] != ""):
            user1.append(GitignoreEntry())
        if generated and user2 and (generated[-1] != "" and user2[0] != ""):
            user2.insert(0, GitignoreEntry())

        return "\n".join(join_generated_section(user1, generated, user2)) + "\n"

    # RenderFileTask

    #: The path to the `.gitignore` file to sync, relative to the task's project directory.
    file: Property[Path] = Property.default(Path(".gitignore"))

    # Task

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.content.setcallable(lambda: self.get_file_contents(self.file.get()))

    def finalize(self) -> None:
        self.file.setmap(lambda file: self.project.directory / file)
        super().finalize()
