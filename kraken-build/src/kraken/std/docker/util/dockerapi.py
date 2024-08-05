from __future__ import annotations

import logging
import os
import subprocess as sp
from pathlib import Path

from kraken.common import flatten

logger = logging.getLogger(__name__)


def docker_run(
    image: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    entrypoint: str | None = None,
    interactive: bool = False,
    remove: bool = True,
    volumes: list[str] | None = None,
    workdir: str | None = None,
    cwd: str | None = None,
    environ: dict[str, str] | None = None,
) -> int:
    command = ["docker", "run"]
    command += flatten(("--env", f"{key}={value}") for key, value in (env or {}).items())
    if platform is not None:
        command += ["--platform", platform]
    if entrypoint is not None:
        command += ["--entrypoint", entrypoint]
    if interactive:
        command += ["-it"]
    if remove:
        command += ["--rm"]
    command += flatten(("--volume", volume) for volume in (volumes or []))
    if workdir:
        command += ["--workdir", workdir]
    command += [image]
    command += args or []
    logger.info("%s", command)
    return sp.call(command, cwd=cwd, env={**os.environ, **(environ or {})})


def docker_load(image_file: Path) -> int:
    """Load a docker image archive by file."""

    command = ["docker", "load", "-i", str(image_file)]
    logger.info("%s", command)
    return sp.call(command)
