import contextlib
import os
from pathlib import Path
from subprocess import DEVNULL, Popen
from time import sleep
from typing import Mapping, Sequence

from kraken.core import BackgroundTask, Property, Task
from kraken.core.system.task import TaskStatus


class RunContainerTask(BackgroundTask):
    """
    Run a container, optionally in the background for as long as dependant tasks are running.
    """

    container_name: Property[str | None] = Property.default(None, help="Name of the container to run")
    image: Property[str] = Property.required(help="Name of the image to run")
    ports: Property[Sequence[str]] = Property.default((), help="Ports to expose")
    env: Property[Mapping[str, str]] = Property.default({}, help="Environment variables to set")
    args: Property[Sequence[str]] = Property.default((), help="Arguments to pass to the container")
    workdir: Property[str | None] = Property.default(None, help="Working directory to set in the container")
    entrypoint: Property[str | None] = Property.default(None, help="Entrypoint to set in the container")

    cwd: Property[Path | None] = Property.default(None, help="Working directory to run the Docker command in")

    _pid: Property[int] = Property.output(help="PID of the container process. Internal use only.")

    # BackgroundTask overrides

    def start_background_task(self, exit_stack: contextlib.ExitStack) -> None:
        command = ["docker", "run", "--rm"]  # , "-it"]
        if container_name := self.container_name.get():
            command.extend(["--name", container_name])
        for port in self.ports.get():
            command.extend(["-p", port])
        for key, value in self.env.get().items():
            command.extend(["-e", f"{key}={value}"])
        if workdir := self.workdir.get():
            command.extend(["-w", workdir])
        if entrypoint := self.entrypoint.get():
            command.extend(["--entrypoint", entrypoint])
        command.append(self.image.get())
        command.extend(self.args.get())

        cwd = self.cwd.get() or Path.cwd()
        self.logger.info("Running command %s in directory %s", command, cwd)

        proc = Popen(
            command,
            shell=False,
            cwd=cwd,
            stdout=DEVNULL,
            stderr=DEVNULL,
        )
        self._pid.set(proc.pid)

        def _stop_proc() -> None:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
                if proc.poll() is None:
                    proc.kill()

        exit_stack.callback(_stop_proc)


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
