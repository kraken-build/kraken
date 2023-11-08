from __future__ import annotations

import contextlib
import logging
import subprocess as sp
import time

import httpx

from kraken.common import flatten
from kraken.std import http

logger = logging.getLogger(__name__)


class DockerServiceManager:
    """Helper for integration tests to start Docker services."""

    def __init__(self, exit_stack: contextlib.ExitStack) -> None:
        self._exit_stack = exit_stack

    def _stop_container(self, container_id: str) -> None:
        sp.call(["docker", "stop", container_id])

    def _run_probe(self, probe_method: str, probe_url: str, timeout: int) -> None:
        logger.info("Probing %s %s (timeout: %d)", probe_method, probe_url, timeout)
        tstart = time.perf_counter()
        while (time.perf_counter() - tstart) < timeout:
            try:
                request = http.request(probe_method, probe_url)
            except httpx.RequestError as exc:
                logger.debug("Ignoring error while probing (%s)", exc)
            else:
                if request.status_code // 100 in (2, 3):
                    logger.info("Probe returned status code %d", request.status_code)
                    return
                logger.debug("Probe returned status code %d (continue probing)", request.status_code)
            time.sleep(0.5)
        raise TimeoutError("Probe timed out")

    def run(
        self,
        image: str,
        args: list[str] | None = None,
        detach: bool = False,
        ports: list[str] | None = None,
        volumes: list[str] | None = None,
        platform: str | None = None,
        env: dict[str, str] | None = None,
        entrypoint: str | None = None,
        capture_output: bool = False,
        probe: tuple[str, str] | None = None,
        probe_timeout: int = 60,
    ) -> bytes | None:
        command = ["docker", "run", "--rm"]
        if detach:
            command += ["-d"]
        if entrypoint:
            command += ["--entrypoint", entrypoint]
        command += flatten(["-p", p] for p in ports or [])
        command += flatten(["-v", v] for v in volumes or [])
        command += flatten(["--env", f"{k}={v}"] for k, v in (env or {}).items())
        if platform:
            command += ["--platform", platform]
        command += [image]
        command += args or []

        logger.info("Running command %s", command)

        if detach:
            container_id = sp.check_output(command).decode().strip()
            logger.info('started detached container with id "%s" from command %s', container_id, command)
            self._exit_stack.callback(self._stop_container, container_id)
            logs_proc = sp.Popen(["docker", "logs", "-f", container_id])

            def _stop_logs_proc() -> None:
                logs_proc.terminate()
                logs_proc.wait()

            self._exit_stack.callback(_stop_logs_proc)

            if probe:
                self._run_probe(probe[0], probe[1], probe_timeout)

        elif capture_output:
            return sp.check_output(command)
        else:
            sp.check_call(command)

        return None
