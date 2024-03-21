import os
import subprocess
from typing import Any
from kraken.common.supplier import Supplier
from kraken.core import Task, Property, TaskStatus


class ShellCmdTask(Task):
    """ Executes a shell command. """

    shell: Property[str | None] = Property.default(None, help="The shell command to execute. Defaults to the $SHELL variable.")
    script: Property[str] = Property.required(help="The script to execute.")
    cwd: Property[str] = Property.default("", help="The working directory to execute the command in.")
    env: Property[dict[str, str]] = Property.default({}, help="The environment variables to set for the command.")

    def execute(self) -> TaskStatus | None:
        shell = self.shell.get() or os.getenv("SHELL") or "sh"
        script = self.script.get()
        cwd = self.cwd.get() or self.project.directory
        env = {**os.environ, **self.env.get()}
        command = [shell, "-c", script]
        return TaskStatus.from_exit_code(
            command,
            subprocess.call(command, env=env, cwd=cwd, stdin=subprocess.DEVNULL),
        )


def shell_cmd(*, name: str, template: str, shell: str | None = None, **kwargs: str | Supplier[str]) -> ShellCmdTask:
    """ Create a task that runs a shell command. The *template* may contain `{key}` placeholders that will be
    replaced with the corresponding value from *kwargs*. """

    from kraken.build import project

    kwargs_suppliers = {k: Supplier.of(v) for k, v in kwargs.items()}
    script = Supplier.of(template, kwargs_suppliers.values()).map(lambda s: s.format(**{k: v.get() for k, v in kwargs_suppliers.items()}))

    task = project.task(name, ShellCmdTask)
    task.shell = shell
    task.script = script
    return task
