from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess as sp
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def helm_package(
    chart_path: Path,
    output_file: Path | None = None,
    output_directory: Path | None = None,
    app_version: str | None = None,
    version: str | None = None,
) -> tuple[int, Path | None]:
    """Package a Helm chart."""

    if output_file is not None and output_directory is not None:
        raise ValueError("output_file and output_directory cannot both be set")

    with contextlib.ExitStack() as exit_stack:
        command = ["helm", "package", str(chart_path)]

        # We build into a temporary directory first.
        tempdir = Path(exit_stack.enter_context(tempfile.TemporaryDirectory()))
        command += ["--destination", str(tempdir)]

        if app_version:
            command += ["--appVersion", app_version]
        if version:
            command += ["--version", version]

        logger.info("%s", command)
        result = sp.call(command)
        if result != 0:
            return result, None

        built_file = list(tempdir.iterdir())
        assert len(built_file) == 1, built_file

        if not output_file:
            assert output_directory is not None
            output_file = output_directory / built_file[0].name
        output_file.parent.mkdir(exist_ok=True, parents=True)
        shutil.move(str(built_file[0]), output_file)

        return 0, output_file

    assert False


def helm_registry_login(registry: str, username: str, password: str, insecure: bool = False) -> tuple[list[str], int]:
    """Log into a Helm registry."""

    command = ["helm", "registry", "login", registry, "-u", username, "--password-stdin"]
    if insecure:
        command += ["--insecure"]
    return command, sp.run(command, input=f"{password}\n".encode()).returncode


def helm_push(chart_tarball: Path, remote: str) -> tuple[list[str], int]:
    """Push a Helm chart to a remote."""

    command = ["helm", "push", str(chart_tarball), remote]
    return command, sp.call(command)
