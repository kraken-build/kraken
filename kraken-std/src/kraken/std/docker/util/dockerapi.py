from __future__ import annotations

import json
import logging
import os
import subprocess as sp
from pathlib import Path
from typing import Any

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


class DockerInspect(dict[str, Any]):
    def get_status(self) -> str:
        return self["State"]["Status"]  # type: ignore[no-any-return]

    def get_labels(self) -> dict[str, str]:
        return self["Config"]["Labels"] or {}


def docker_inspect(container_name: str) -> DockerInspect | None:
    """Inspect a docker container by name."""

    command = ["docker", "container", "inspect", container_name]
    try:
        output = sp.check_output(command, text=True, stderr=sp.DEVNULL)
    except sp.CalledProcessError as e:
        if e.returncode == 1:
            return None
        raise

    return DockerInspect(json.loads(output)[0])


def docker_rm(container_name: str, not_exist_ok: bool = False) -> None:
    command = ["docker", "rm", container_name]
    try:
        sp.run(command, check=True, stderr=sp.DEVNULL)
    except sp.CalledProcessError as e:
        if e.returncode == 1 and not_exist_ok:
            return
        raise


def docker_start(container_name: str) -> None:
    command = ["docker", "start", container_name]
    sp.run(command, check=True, stderr=sp.DEVNULL)


def docker_stop(container_name: str, not_exist_ok: bool = False) -> bool:
    command = ["docker", "stop", container_name]
    try:
        sp.run(command, check=True, stderr=sp.DEVNULL)
        return True
    except sp.CalledProcessError as e:
        if e.returncode == 1 and not_exist_ok:
            return False
        raise
