from __future__ import annotations

import logging
import re
import subprocess as sp

from kraken.core import Property, Task, TaskStatus


class CargoCheckToolchainVersionTask(Task):
    description = "Ensures that Cargo (and so, Rust) is at least at the given version"

    minimal_version: Property[str]

    def execute(self) -> TaskStatus:
        minimal_version = self.minimal_version.get()

        # we fetch Cargo version
        try:
            result = sp.check_output(["cargo", "--verbose", "--version"]).decode()
            cargo_metadata = {key: value for key, value in re.findall(r"^([a-z]+):\s+(.*)\s*$", result, re.MULTILINE)}
        except sp.CalledProcessError as e:
            logging.error(f"Rust Cargo tool returned error code {e.returncode}, are you sure it is properly installed?")
            logging.info("You can install cargo using https://rustup.rs/ or `brew install rustup-init` on macOS")
            return TaskStatus.failed("cargo not found")
        if "release" not in cargo_metadata:
            return TaskStatus.failed("No release found in cargo metadata")
        cargo_version = cargo_metadata["release"]

        try:
            parsed_cargo_version = self._parse_version(cargo_version)
        except ValueError:
            return TaskStatus.failed(f"Invalid cargo version: {cargo_version}")
        try:
            parsed_minimal_version = self._parse_version(minimal_version)
        except ValueError:
            return TaskStatus.failed(f"Invalid expected version: {minimal_version}")

        # Hack: the order on Python tuples is the lexicographic order, the one we want here
        if parsed_minimal_version > parsed_cargo_version:
            logging.warning(
                f"The cargo version is outdated. Expecting at least {minimal_version} but found {cargo_version}"
            )
            logging.info("Please upgrade cargo using `rustup update`")
            return TaskStatus.failed(f"Outdated version {cargo_version}")

        return TaskStatus.succeeded()

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        return tuple(int(e) for e in version.split("-")[0].split("."))
