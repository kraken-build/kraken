import contextlib
import os
import shlex
from pathlib import Path
from subprocess import DEVNULL, Popen
from time import sleep
from typing import Mapping, Sequence

from kraken.core import BackgroundTask, Property, Task
from kraken.core.system.task import TaskStatus

from kraken.std.docker.util.dockerapi import docker_inspect, docker_rm, docker_start, docker_stop


class RunContainerTask(BackgroundTask):
    """
    Run a container, optionally in the background for as long as dependant tasks are running.

    If the container is configured to run detached, it will not be terminated when the task is stopped.
    """

    container_name: Property[str] = Property.required(help="Name of the container to run")
    image: Property[str] = Property.required(help="Name of the image to run")
    ports: Property[Sequence[str]] = Property.default((), help="Ports to expose")
    env: Property[Mapping[str, str]] = Property.default({}, help="Environment variables to set")
    args: Property[Sequence[str]] = Property.default((), help="Arguments to pass to the container")
    workdir: Property[str | None] = Property.default(None, help="Working directory to set in the container")
    entrypoint: Property[str | None] = Property.default(None, help="Entrypoint to set in the container")
    detach: Property[bool] = Property.default(True, help="Whether to run the container in the background")

    cwd: Property[Path | None] = Property.default(None, help="Working directory to run the Docker command in")

    _pid: Property[int] = Property.output(help="PID of the container process. Internal use only.")

    _LABEL_NAME = "kraken.container.command"

    # BackgroundTask overrides

    def start_background_task(self, exit_stack: contextlib.ExitStack) -> TaskStatus:
        cwd = (self.cwd.get() or self.project.directory).absolute()

        command = ["docker", "run", "--rm"]
        container_name = self.container_name.get()
        command.extend(["--name", container_name])
        for port in self.ports.get():
            command.extend(["-p", port])
        for key, value in self.env.get().items():
            command.extend(["-e", f"{key}={value}"])
        if workdir := self.workdir.get():
            command.extend(["-w", workdir])
        if entrypoint := self.entrypoint.get():
            command.extend(["--entrypoint", entrypoint])
        if detach := self.detach.get():
            command.append("-d")
        command.append(self.image.get())
        command.extend(self.args.get())

        command_as_string = " ".join(map(shlex.quote, command)) + f" || in cwd: {cwd}"

        existing_container = docker_inspect(container_name)
        if (
            existing_container is not None
            and existing_container.get_labels().get(self._LABEL_NAME) == command_as_string
            and existing_container.get_status() == "running"
        ):
            return TaskStatus.skipped("Container %s is already running" % container_name)

        if (
            existing_container is not None
            and existing_container.get_labels().get(self._LABEL_NAME) != command_as_string
        ):
            print(f"Rerunning container {container_name!r} (definition changed)")
            if existing_container.get_status() == "running":
                docker_stop(container_name)
            docker_rm(container_name, not_exist_ok=True)

        elif existing_container and existing_container.get_status() != "started":
            print(f"Starting container {container_name} (it had stopped)", container_name)
            docker_start(container_name)
            return TaskStatus.succeeded("Container %s started again" % container_name)

        self.logger.info("Running command %s in directory %s", command, cwd)
        command[2:2] = ["-l", f"{self._LABEL_NAME}={command_as_string}"]
        self.logger.debug("Actual command is: %s", command)

        proc = Popen(
            command,
            shell=False,
            cwd=cwd,
            stdout=None if detach else DEVNULL,
            stderr=None if detach else DEVNULL,
        )
        self._pid.set(proc.pid)

        def _stop_proc() -> None:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
                if proc.poll() is None:
                    proc.kill()

        if self.detach.get():
            returncode = proc.wait()
            if returncode == 0:
                return TaskStatus.succeeded("Container %s started" % container_name)
            else:
                return TaskStatus.failed("Container %s could not be started" % container_name)
        else:
            exit_stack.callback(_stop_proc)
            return TaskStatus.succeeded("Container %s start" % container_name)


class StopContainerTask(Task):
    """
    Stops a container.
    """

    container_name: Property[str] = Property.required(help="The name of the container to stop.")

    def execute(self) -> TaskStatus | None:
        if docker_stop(self.container_name.get(), not_exist_ok=True):
            return TaskStatus.succeeded("Container %s stopped" % self.container_name.get())
        else:
            return TaskStatus.skipped("Container %s not found" % self.container_name.get())


class WaitForProcessTask(Task):
    """
    Waits for a process to terminate, or terminates it upon receiving an interrupt signal.
    """

    pid: Property[int] = Property.required(help="PID of the process to wait for")
    check_interval: Property[float] = Property.default(1.0, help="Interval between checks for the process")

    # Task overrides

    def execute(self) -> TaskStatus | None:
        try:
            while True:
                try:
                    os.kill(self.pid.get(), 0)
                except OSError:
                    break
                sleep(self.check_interval.get())
        except KeyboardInterrupt:
            os.kill(self.pid.get(), 2)
            raise
        return TaskStatus.succeeded("Process %d terminated" % self.pid.get())
