from __future__ import annotations

import logging
import shutil
import subprocess as sp

from kraken.core import Property, Task, TaskStatus
from kraken.std.cargo.config import CargoConfig

logger = logging.getLogger(__name__)


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

    def get_command(self) -> list[str]:
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
        if CargoFmtTask.is_using_rust_nightly():
            # if a nightly version of rust is used, then it is in the toolchains
            return TaskStatus.succeeded()

        # if the current version of rust is not nightly, we try to find a nightly toolchain with the correct
        # architecture
        # this is a best effort check to return a helpful error message by checking if available toolchains, which is
        # only possible if rustup is installed
        rustup = shutil.which("rustup")
        if rustup is None:
            return TaskStatus.succeeded()

        result = sp.run([rustup, "show", "active-toolchain"], stdout=sp.PIPE, stderr=sp.DEVNULL)
        if result.returncode != 0:
            return TaskStatus.failed("could not determine the active rust toolchain")

        output = result.stdout.decode("utf-8").split(" ")
        architecture = "-".join(output[0].split("-")[-3:])

        result = sp.run([rustup, "show"], stdout=sp.PIPE, stderr=sp.DEVNULL)
        if result.returncode != 0:
            return TaskStatus.failed("could not determine available toolchains")

        if any(
            [
                toolchain.startswith("nightly-") and toolchain.endswith(architecture)
                for toolchain in result.stdout.decode("utf-8").splitlines()
            ]
        ):
            return TaskStatus.succeeded()

        formatted_command = " ".join(self.get_command())
        return TaskStatus.failed(
            f"cannot run `{formatted_command}` with nightly toolchain because it is not installed, either install it or"
            + " opt-out of the nightly toolchain with `cargo_config(nightly=False)`"
        )

    @staticmethod
    def is_using_rust_nightly() -> bool:
        rustc = shutil.which("rustc")
        if rustc is None:
            logger.warn("rustc is not installed, could not determine the active rust version")
            return False

        result = sp.run([rustc, "--version"], stdout=sp.PIPE, stderr=sp.DEVNULL)
        if result.returncode != 0:
            logger.warn("rustc --version is not installed, could not determine the active rust version")
            return False

        return "-nightly" in result.stdout.decode("utf-8")

    def get_description(self) -> str | None:
        formatted_command = " ".join(self.get_command())
        return f"Run `{formatted_command}`."
