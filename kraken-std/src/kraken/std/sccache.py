from __future__ import annotations

import contextlib
import dataclasses
import os
import re
import shutil
import subprocess as sp
from pathlib import Path
from typing import Any

from kraken.core import BackgroundTask, Project, Property, TaskStatus


@dataclasses.dataclass
class AzureBlobStorageCache:
    connection_string: str
    container_name: str
    key_prefix: str | None = None

    def to_env(self) -> dict[str, str]:
        environ = {
            "SCCACHE_AZURE_CONNECTION_STRING": self.connection_string,
            "SCCACHE_AZURE_BLOB_CONTAINER": self.container_name,
        }
        if self.key_prefix is not None:
            environ["SCCACHE_AZURE_KEY_PREFIX"] = self.key_prefix
        return environ


@dataclasses.dataclass
class LocalCache:
    cache_dir: Path | None = None

    def to_env(self) -> dict[str, str]:
        environ = {}
        if self.cache_dir:
            environ["SCCACHE_DIR"] = str(self.cache_dir.absolute())
        return environ


@dataclasses.dataclass
class SccacheManager:
    cache_config: AzureBlobStorageCache | LocalCache | None
    log_level: str | None = None
    log_file: Path | None = None
    bin: Path | None = None

    def __post_init__(self) -> None:
        self._proc: sp.Popen[Any] | None = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    def get_cache_location(self) -> str:
        stats = self.stats()
        match = re.search(r"^Cache\s+location\s+(.*)$", stats, re.I | re.M)
        assert match is not None, f"Could not determine cache location from sccache stats output: {stats!r}"
        return match.group(1)

    def start(self) -> None:
        """Start the Sccache server."""

        if self.is_running():
            assert self._proc is not None
            raise RuntimeError(f"Sccache is already running (pid: {self._proc.pid})")

        command = [str(self.bin) if self.bin else "sccache"]
        env = {}
        if self.cache_config:
            env.update(self.cache_config.to_env())
        if self.log_level is not None:
            env["SCCACHE_LOG"] = self.log_level
        if self.log_file is not None:
            env["SCCACHE_ERROR_LOG"] = str(self.log_file.absolute())
        env["SCCACHE_START_SERVER"] = "1"
        self._proc = sp.Popen(command, env={**os.environ, **env})

    def stats(self) -> str:
        command = [str(self.bin) if self.bin else "sccache", "-s"]
        return sp.check_output(command).decode()

    def stop(self, show_stats: bool = False) -> None:
        """Stop the Sccache server."""

        if not self.is_running():
            return
        assert self._proc is not None

        env = {"SCCACHE_NO_DAEMON": "1"}
        command = [str(self.bin) if self.bin else "sccache", "--stop-server"]
        sp.check_call(command, env={**os.environ, **env}, stdout=None if show_stats else sp.DEVNULL)

        self._proc.wait(10)
        if self.is_running():
            self._proc.terminate()


def find_sccache() -> Path | None:
    sccache = shutil.which("sccache")
    if sccache is not None:
        return Path(sccache)
    return None


class SccacheTask(BackgroundTask):
    """This task ensures that an Sccache server is running for all its dependant tasks."""

    description = "Start sccache in the background."
    manager: Property[SccacheManager]

    def start_background_task(self, exit_stack: contextlib.ExitStack) -> TaskStatus:
        manager = self.manager.get()
        if not manager.is_running():
            manager.start()
        exit_stack.callback(lambda: manager.stop(show_stats=True))
        return TaskStatus.started(manager.get_cache_location())


def sccache(
    manager: SccacheManager,
    *,
    name: str = "sccache",
    group: str | None = None,
    project: Project | None = None,
) -> SccacheTask:
    """Creates a background task that starts the sccache server."""

    project = project or Project.current()
    return project.do(name, SccacheTask, False, group=group, manager=manager)
