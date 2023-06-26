from __future__ import annotations

from kraken.std.git.version import GitVersion

_PRE_RELEASE_NAMES = {
    GitVersion.PreRelease.Kind.ALPHA: "a",
    GitVersion.PreRelease.Kind.BETA: "b",
    GitVersion.PreRelease.Kind.RC: "rc",
}


def git_version_to_python_version(value: str | GitVersion, include_sha: bool) -> str:
    """Converts a Git version to a Python version.

    :param value: The Git version to convert.
    :param sha: Include the SHA of the commit distance if it exists.
    """

    version = GitVersion.parse(value) if isinstance(value, str) else value
    final_version = f"{version.major}.{version.minor}.{version.patch}"
    if version.pre_release:
        final_version = f"{final_version}{_PRE_RELEASE_NAMES[version.pre_release.kind]}{version.pre_release.value}"
    if version.distance:
        final_version += f".post0.dev{version.distance.value}"
        if include_sha:
            final_version += f"+g{version.distance.sha}"
            if version.dirty:
                final_version += "-dirty"
    if version.dirty and "-dirty" not in final_version:
        final_version += "+dirty"
    return final_version
