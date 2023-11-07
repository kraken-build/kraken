from __future__ import annotations

import shutil
import subprocess as sp
from os.path import realpath

from kraken.core import Property, Task, TaskStatus


class RustupTargetAddTask(Task):
    description = "Installs a given target for Cargo. Skipped if Cargo was installed by Nix."

    target: Property[str]

    def execute(self) -> TaskStatus:
        cargo_path = shutil.which("cargo")
        if cargo_path is not None:
            cargo_real_path = realpath(cargo_path)

            if cargo_real_path.startswith("/nix/"):
                return TaskStatus.skipped()

        command = ["rustup", "target", "add", self.target.get()]
        result = sp.call(command, cwd=self.project.directory)
        return TaskStatus.from_exit_code(command, result)
