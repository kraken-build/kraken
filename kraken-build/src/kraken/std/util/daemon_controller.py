import errno
import json
import logging
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Any, Literal

logger = logging.getLogger(__name__)


def process_exists(pid: int) -> bool:
    """Checks if the processed with the given *pid* exists. Returns #True if
    that is the case, #False otherwise."""

    if pid == 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
    return True


def wait_for_child_process(pid: int, timeout: float, interval: float = 0.1) -> int | None:
    """Wait for the process of *pid* to exit and return the exit code. This only works for child processes."""

    tstart = time.perf_counter()
    while (time.perf_counter() - tstart) < timeout:
        (pid_returned, status) = os.waitpid(pid, os.WNOHANG)
        if pid_returned != 0:
            return os.waitstatus_to_exitcode(status)
        time.sleep(interval)
    return None


def wait_for_process(pid: int, timeout: float, interval: float = 0.1) -> bool:
    """Wait for a process to exit. Returns True if the process exited within the timeout period."""

    tstart = time.perf_counter()
    while (time.perf_counter() - tstart) < timeout:
        if not process_exists(pid):
            return True
        time.sleep(interval)
    return False


def process_terminate(
    pid: int,
    allow_kill: bool = True,
    sigint_timeout: float = 3.0,
    sigterm_timeout: float = 2.0,
    sigkill_timeout: float = 1.0,
) -> bool:
    """Terminates the process with the given *pid*. First sends #signal.SIGINT,
    followed by #signal.SIGTERM after *sigint_timeout* seconds, followed by
    #signal.SIGKILL after *sigkill_timeout* seconds if the process has not responded to
    the terminate signal.

    The fallback to kill can be disabled by setting *allow_kill* to False.
    Returns True if the process was successfully terminated or killed, or if
    the process did not exist in the first place."""

    try:
        os.kill(pid, signal.SIGINT)
        if wait_for_process(pid, sigint_timeout) is not None:
            return True
        os.kill(pid, signal.SIGTERM)
        if wait_for_process(pid, sigterm_timeout) is not None:
            return True
        if allow_kill:
            os.kill(pid, signal.SIGKILL)
            return wait_for_process(pid, sigkill_timeout) is not None
        return False
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return True
        raise


def spawn_fork(func: Callable[[], Any], detach: bool = True) -> int:
    """Spawns a single fork process and calls *func*. If *detach* is #True,
    the fork will be detached first (note that this process will still be killed
    by it's parent process if it doesn't exist gracefully).

    This is useful if *func* spawns another process, which will then behave like
    a daemon (as it will NOT be killed if the original process dies)."""

    if not callable(func):
        raise TypeError(f"func is of type {type(func).__name__} which is not callable")

    pid = os.fork()
    if pid > 0:
        # Return to the original caller
        return pid
    if detach:
        os.setsid()
    try:
        func()
    finally:
        os._exit(os.EX_OK)


def replace_stdio(stdin: int | None = None, stdout: int | None = None, stderr: int | None = None) -> None:
    """Replaces the file handles of stdin/sdout/stderr, closing the original file descriptors if necessary."""

    if stdin is not None:
        os.dup2(stdin, sys.stdin.fileno())
    if stdout is not None:
        os.dup2(stdout, sys.stdout.fileno())
    if stderr is not None:
        os.dup2(stderr, sys.stderr.fileno())


class DaemonController:
    """
    Manages a daemon process. If the process isn't running, or the configuration of the process changed, it will be
    restarted.

    :param state_file: The file where the daemon state, such as the PID and the arguments that the daemon was started
        with, is stored. If the file does not exist, it will be assumed that the daemon is not running. This file
        is mandatory for the controller.
    """

    @dataclass(frozen=True)
    class State:
        command: list[str]
        cwd: str
        env: dict[str, str]
        pid: int
        started_at: float

    def __init__(self, name: str, state_file: Path) -> None:
        self.name = name
        self.state_file = state_file

    def load_state(self) -> State | None:
        try:
            data = json.loads(self.state_file.read_text())
        except FileNotFoundError:
            return None
        except json.JSONDecodeError:
            logger.warning("Could not decode Daemon %r state file. Continuing as if it did not exist.", self.name)
            return None
        try:
            return self.State(**data)
        except TypeError:
            if "pid" in data and isinstance(data["pid"], int):
                logger.warning(
                    "Could not initialize Daemon %r state from payload, but a `pid` field was found. Continuing "
                    "with a state that does not contain any information besides the `pid`.",
                    self.name,
                )
                return self.State([], os.getcwd(), {}, data["pid"], 0)
            else:
                logger.error(
                    "Could not recover from invalid JSON payload found for Daemon %r state. Continuing as if it "
                    "did not exist.",
                    self.name,
                )
            return None

    def save_state(self, state: State) -> None:
        self.state_file.write_text(json.dumps(asdict(state)))

    def remove_state(self) -> None:
        try:
            self.state_file.unlink()
        except FileNotFoundError:
            pass

    def is_alive(self) -> bool:
        state = self.load_state()
        return bool(state is not None and process_exists(state.pid))

    def run(
        self,
        command: list[str],
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        stdout: Path | None = None,
        stderr: Path | None | Literal["stdout"] = "stdout",
        mkdir: bool = True,
    ) -> bool:
        """
        Ensure that the daemon is running. If the command or cwd changed, the daemon will be restarted. Returns True
        if the daemon was started, False if it was already running.
        """

        if stderr is not None and stderr != "stdout":
            assert isinstance(stderr, Path), type(stderr)
            stderr_path = stderr.absolute()
        else:
            stderr_path = None
        stderr_to_stdout = stderr == "stdout"

        cwd = cwd.absolute() if cwd else Path.cwd()
        env = dict(env.items()) if env else {}
        stdout = stdout.absolute() if stdout else None

        state = self.load_state()
        daemon_alive = bool(state and process_exists(state.pid))
        if daemon_alive and state and state.command == command and state.cwd == str(cwd) and env == state.env:
            logger.info("Daemon %r is already running (pid: %s)", self.name, state.pid)
            return False

        if state and daemon_alive:
            logger.info("Restarting daemon %r.", self.name)
            process_terminate(state.pid)
            self.remove_state()
            state = None
        else:
            logger.info("Starting daemon %r.", self.name)

        def start_daemon() -> None:
            if stdout is not None:
                if mkdir:
                    stdout.parent.mkdir(parents=True, exist_ok=True)
                stdout_fp: IO[Any] | int = stdout.open("wb")
            else:
                stdout_fp = subprocess.DEVNULL

            if stderr_to_stdout:
                stderr_fp: IO[Any] | int = stdout_fp
            elif stderr_path:
                if mkdir:
                    stderr_path.parent.mkdir(parents=True, exist_ok=True)
                stderr_fp = stderr_path.open("wb")
            else:
                stderr_fp = subprocess.DEVNULL

            proc_env = os.environ.copy()
            proc_env.update(env)
            proc = subprocess.Popen(command, cwd=cwd, env=proc_env, stdout=stdout_fp, stderr=stderr_fp)
            logger.info("Daemon %r started (pid: %s)", self.name, proc.pid)
            state = self.State(command, str(cwd), env, proc.pid, time.time())
            self.save_state(state)

        logger.debug("Spawning fork to start daemon %s", self.name)
        pid = spawn_fork(start_daemon)
        if status := wait_for_child_process(pid, 10.0):
            raise Exception("An unexpected error ocurred when starting daemon %r (exit code %s).", self.name, status)
        return True

    def stop(self) -> bool:
        """
        Stop the daemon if it is currently running. Returns True if the daemon was running and is now stopped.
        """

        state = self.load_state()
        if state and process_exists(state.pid):
            logger.info("Stopping daemon %r.", self.name)
            process_terminate(state.pid)
            self.remove_state()
            return True

        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
    controller = DaemonController("cli", Path("cli-daemon.state"))
    if len(sys.argv) == 1:
        if not controller.stop():
            logger.warning("Daemon was not running.")
    else:
        controller.run(sys.argv[1:], Path.cwd(), {}, Path("cli-daemon.txt"), "stdout")
