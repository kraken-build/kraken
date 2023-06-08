from __future__ import annotations

import subprocess as sp
from typing import List

from kraken.core import Property, Task, TaskStatus

from kraken.std.cargo.config import CargoConfig


class CargoFmtTask(Task):
    check: Property[bool] = Property.default(False)
    all_packages: Property[bool] = Property.default(False)
    config: Property[CargoConfig]

    def execute(self) -> TaskStatus:
        nightly = self.config.get().nightly
        if nightly:
            result = self.check_nightly_toolchain()
            if result.is_not_ok():
                return result

        command = self.get_command()

        return TaskStatus.from_exit_code(command, sp.call(command, cwd=self.project.directory))

    def get_command(self) -> List[str]:
        command = ["cargo"]

        if self.config.get().nightly:
            command.append("+nightly")

        command.append("fmt")

        if self.check.get():
            command.append("--check")
        if self.all_packages.get():
            command.append("--all")

        return command

    def check_nightly_toolchain(self) -> TaskStatus:
        result = sp.run(["rustup", "show", "active-toolchain"], stdout=sp.PIPE, stderr=sp.DEVNULL)
        if result.returncode != 0:
            return TaskStatus.failed("could not determine the active rust toolchain")

        if result.stdout.decode("utf-8").startswith("nightly-"):
            return TaskStatus.succeeded()

        formatted_command = " ".join(self.get_command())
        return TaskStatus.failed(
            f"cannot run `{formatted_command}` with nightly toolchain because it is not active, either install it or "
            + "opt-out of the nightly toolchain with `cargo_config(nightly=False)`"
        )

    def get_description(self) -> str | None:
        formatted_command = " ".join(self.get_command())
        return f"Run `{formatted_command}`."
