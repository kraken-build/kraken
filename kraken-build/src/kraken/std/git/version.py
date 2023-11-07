from __future__ import annotations

import dataclasses
import enum
import re
import subprocess as sp
from pathlib import Path


def git_describe(path: Path | None, tags: bool = True, dirty: bool = True) -> str:
    """Describe a repository with tags.

    :param path: The directory in which to describe.
    :param tags: Whether to include tags (adds the `--tags` flag).
    :param dirty: Whether to include if the directory tree is dirty (adds the `--dirty` flag).
    :raise ValueError: If `git describe` failed.
    :return: The Git head description.
    """

    command = ["git", "describe"]
    if tags:
        command.append("--tags")
    if dirty:
        command.append("--dirty")
    try:
        return sp.check_output(command, cwd=path).decode().strip()
    except sp.CalledProcessError:
        count = int(sp.check_output(["git", "rev-list", "HEAD", "--count"], cwd=path).decode().strip())
        short_rev = sp.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=path).decode().strip()
        return f"0.0.0-{count}-g{short_rev}"


@dataclasses.dataclass
class GitVersion:
    """Represents a "git version" that has a major, minor and patch version and optionally a commit distance."""

    @dataclasses.dataclass
    class PreRelease:
        @enum.unique
        class Kind(str, enum.Enum):
            ALPHA = "alpha"
            BETA = "beta"
            RC = "rc"

        kind: Kind
        value: int

    @dataclasses.dataclass
    class CommitDistance:
        value: int
        sha: str

    major: int
    minor: int
    patch: int
    pre_release: PreRelease | None
    distance: CommitDistance | None
    dirty: bool

    @staticmethod
    def parse(value: str) -> GitVersion:
        GIT_VERSION_REGEX = r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc).(\d+))?(?:-(\d+)-g(\w+))?(-dirty)?$"
        match = re.match(GIT_VERSION_REGEX, value)
        if not match:
            raise ValueError(f"not a valid GitVersion: {value!r}")
        if match.group(4):
            pre_release = GitVersion.PreRelease(
                kind=GitVersion.PreRelease.Kind(match.group(4)), value=int(match.group(5))
            )
        else:
            pre_release = None
        if match.group(6):
            distance = GitVersion.CommitDistance(value=int(match.group(6)), sha=match.group(7))
        else:
            distance = None
        return GitVersion(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            pre_release=pre_release,
            distance=distance,
            dirty=match.group(8) is not None,
        )

    def format(self, distance: bool = True, sha: bool = True, dirty: bool = False) -> str:
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            result = f"{result}-{self.pre_release.kind.value}.{self.pre_release.value}"
        if self.distance and distance:
            result = f"{result}-{self.distance.value}"
            if sha:
                result = f"{result}-g{self.distance.sha}"
            if self.dirty and dirty:
                result = f"{result}-dirty"
        return result
