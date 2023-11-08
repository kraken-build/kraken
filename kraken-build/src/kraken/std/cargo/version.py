from __future__ import annotations

from kraken.std.git import GitVersion


def git_version_to_cargo_version(version: str | GitVersion, include_sha: bool) -> str:
    """Constructs a Cargo version from a Git version."""

    version = GitVersion.parse(version) if isinstance(version, str) else version
    cargo_version = f"{version.major}.{version.minor}.{version.patch}"
    if version.pre_release:
        cargo_version = f"{cargo_version}-{version.pre_release.kind.value}.{version.pre_release.value}"
    if version.distance:
        cargo_version = f"{cargo_version}-dev{version.distance.value}"
        if include_sha:
            cargo_version = f"{cargo_version}+{version.distance.sha}"
    return cargo_version
