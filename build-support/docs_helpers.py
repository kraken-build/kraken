from subprocess import run
from pathlib import Path
from typing import Literal
from kraken.core import Task, TaskStatus, Property
import os


class DocsVenvTask(Task):
    directory: Property[Path]

    def prepare(self) -> TaskStatus | None:
        directory = self.directory.get()
        if directory.is_dir():
            return TaskStatus.skipped("docs-venv exists")

    def execute(self) -> TaskStatus | None:
        directory = self.directory.get()
        if not directory.is_dir():
            run(["python3", "-m", "venv", directory])
            run([directory / "bin" / "pip", "install", "-r", self.project.directory / "requirements.txt"])


class DocsTask(Task):
    venv: Property[Path]
    mode: Property[Literal["serve", "build"]]

    def execute(self) -> TaskStatus | None:
        venv = self.venv.get().absolute()
        command = [str(venv / "bin" / "novella")]
        if self.mode.get() == "serve":
            command += ["--serve"]
        env = os.environ.copy()
        env["PATH"] = str(venv / "bin") + os.pathsep + env["PATH"]
        run(command, cwd=self.project.directory, env=env)
