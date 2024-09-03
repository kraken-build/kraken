"""
Basic parser for the contents of `.gitignore` files, not to evaluate them but to modify them while keeping some
semblence of structure evoked by comments in the file intact.
"""

from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from itertools import islice
from os import PathLike
from pathlib import Path
from typing import Literal, NamedTuple


class GitignoreEntry(str):
    @property
    def type(self) -> Literal["comment", "blank", "path"]:
        if not self:
            return "blank"
        if self.startswith("#"):
            return "comment"
        return "path"


class GitignoreFile(list[GitignoreEntry]):
    """
    Represents a `.gitignore` file, keeping track of the entries and the generated content.
    """

    def find_comment(self, comment: str) -> int | None:
        return next((i for i, e in enumerate(self) if e.type == "comment" and e.lstrip("#").strip() == comment), None)

    def paths(self, start: int | None = None, stop: int | None = None) -> Iterable[str]:
        return (entry for entry in islice(self, start, stop) if entry.type == "path")

    def add_comment(self, comment: str, index: int | None = None) -> None:
        assert "\n" not in comment
        entry = GitignoreEntry("# " + comment)
        self.insert(len(self) if index is None else index, entry)

    def add_blank(self, index: int | None = None) -> None:
        entry = GitignoreEntry()
        self.insert(len(self) if index is None else index, entry)

    def add_path(self, path: str, index: int | None = None) -> None:
        assert "\n" not in path
        entry = GitignoreEntry(path)
        assert entry.type == "path", entry
        self.insert(len(self) if index is None else index, entry)

    def remove_path(self, path: str) -> None:
        removed = 0
        while True:
            index = next((i for i, e in enumerate(self) if e.type == "path" and e == path), None)
            if index is None:
                break
            del self[index]
            removed += 1
        if removed == 0:
            raise ValueError(f'"{path}" not in GitignoreFile')

    def sort_gitignore(self, sort_paths: bool = True, sort_groups: bool = False) -> None:
        """
        Sorts the entries in the gitignore file, keeping paths under a common comment block grouped.
        Will also get rid of any extra blanks.

        :param gitignore: The input to sort.
        :param sort_paths: Whether to sort paths (default: True).
        :param sort_groups: Whether to sort groups among themselves, not just paths within groups (default: False).
        :return: A new, sorted gitignore file.
        """

        class Group(NamedTuple):
            comments: list[str]
            paths: list[str]

        # List of (comments, paths).
        groups: list[Group] = [Group([], [])]

        for entry in self:
            if entry.type == "path":
                groups[-1].paths.append(entry)
            elif entry.type == "comment":
                # If we already have paths in the current group, we open a new group.
                if groups[-1].paths:
                    groups.append(Group([entry], []))
                # Otherwise we append the comment to the group.
                else:
                    groups[-1].comments.append(entry)

        if sort_groups:
            groups.sort(key=lambda g: "\n".join(g.comments).lower())

        self.clear()
        self.add_blank()  # separate GENERATED from USER content
        for group in groups:
            if sort_paths:
                group.paths.sort(key=str.lower)
            for comment in group.comments:
                self.add_comment(comment)
            for path in group.paths:
                self.add_path(path)
            self.add_blank()

        if self and self[-1].type == "blank":
            self.pop()

    @staticmethod
    def parse(file: Path | str | Iterable[str]) -> GitignoreFile:
        match file:
            case str():
                return GitignoreFile.parse(StringIO(file))
            case PathLike():
                with file.open() as fp:
                    return GitignoreFile.parse(fp)

        gitignore = GitignoreFile()
        for line in file:
            line = line.rstrip("\n")
            if line.strip():
                gitignore.append(GitignoreEntry(line))
            else:
                gitignore.append(GitignoreEntry())
        return gitignore
