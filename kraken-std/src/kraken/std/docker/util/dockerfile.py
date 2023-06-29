from __future__ import annotations

import base64
import json
from collections.abc import Mapping


def render_docker_auth(auth: Mapping[str, tuple[str, str]], indent: int | None = None) -> str:
    """Generates a Docker auth config as JSON."""

    return json.dumps(
        {
            "auths": {
                index: {"auth": base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")}
                for index, (username, password) in auth.items()
            }
        },
        indent=indent,
    )


def update_run_commands(
    dockerfile_content: str, prefix: str, suffix: str = "", only_for_root_user: bool = False
) -> str:
    """Prepends a prefix and appends a suffix string to all `RUN` commands in a Dockerfile.

    If *only_for_root_user* is enabled, the prefix and suffix will only be added if the `RUN` command is executed as
    root. We have to use a heuristic to determine whether a command is executed as root, which is described by the
    following logic:

    * All run commands are assumed to be executed as root by default.
    * If a `USER` command is encountered, the user is set to the specified user. If that user is `root`, we consider
      all following `RUN` commands to be executed as root.

    If you start from a base image that is not running as root, and the prefix and/or suffix can only be run for root,
    your Dockerfile must contain a `USER root` command before the `RUN` commands that require the prefix and/or suffix,
    or explicitly set the non-root user.
    """

    lines = dockerfile_content.splitlines()
    in_run_command = False
    current_user = "root"
    for idx, line in enumerate(lines):
        if line.startswith("RUN ") or in_run_command:
            if only_for_root_user and current_user not in ("root", "0"):
                continue
            if not in_run_command:
                line = "RUN " + prefix + line[4:]
            if line.endswith("\\"):
                in_run_command = True
            elif not line.lstrip().startswith("#"):
                line = line + suffix
                in_run_command = False
            lines[idx] = line
        elif line.startswith("USER"):
            current_user = line.split(maxsplit=1)[1].strip()
    return "\n".join(lines)
