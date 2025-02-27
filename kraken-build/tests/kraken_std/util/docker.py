from __future__ import annotations

import contextlib
import json
import logging
import subprocess as sp
from typing import Any, TypeAlias, TypedDict, cast

from kraken.common import flatten

logger = logging.getLogger(__name__)


class DockerServiceManager:
    """Helper for integration tests to start Docker services."""

    def __init__(self, exit_stack: contextlib.ExitStack) -> None:
        self._exit_stack = exit_stack

    def _stop_container(self, container_id: str) -> None:
        sp.call(["docker", "stop", container_id])

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
    ) -> Container:
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

            inspect_data = json.loads(sp.check_output(["docker", "inspect", container_id]).decode())[0]
            assert isinstance(inspect_data, dict), type(inspect_data)
            return Container(cast(dict[str, Any], inspect_data), None)

        elif capture_output:
            return Container(None, sp.check_output(command))
        else:
            sp.check_call(command)
            return Container(None, None)


class Container:
    PortPlusProtocol: TypeAlias = str

    class ContainerPort(TypedDict):
        HostIp: str
        HostPort: str

    ContainerPorts = dict[PortPlusProtocol, list[ContainerPort]]

    def __init__(self, data: dict[str, Any] | None, output: bytes | None) -> None:
        self._data = data
        self._output = output

    @property
    def ports(self) -> ContainerPorts:
        assert self._data is not None, "Not a live container"
        return cast(Container.ContainerPorts, self._data["NetworkSettings"]["Ports"])

    @property
    def output(self) -> bytes:
        assert self._output is not None, "Did not capture output of container"
        return self._output

    def stop(self) -> None:
        """Stop the container"""
        assert self._data is not None, "Not a live container"
        sp.call(["docker", "stop", cast(str, self._data["Id"])])
