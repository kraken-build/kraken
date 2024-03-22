from __future__ import annotations

import logging
import subprocess as sp

from kraken.core import Property, Task, TaskStatus

logger = logging.getLogger(__name__)


class BuffrsLoginTask(Task):
    """This task logs into artifactory with buffrs"""

    description = "Login to artifactory with buffrs."
    registry: Property[str] = Property.required(
        help="The Artifactory URL to publish to (e.g. `https://<domain>/artifactory`)."
    )
    token: Property[str] = Property.required(help="The token for the registry.")
    buffrs_bin: Property[str] = Property.default("buffrs", help="The path to the buffrs binary.")

    def execute(self) -> TaskStatus:
        command = [self.buffrs_bin.get(), "login", "--registry", self.registry.get()]
        return TaskStatus.from_exit_code(
            command,
            sp.run(command, cwd=self.project.directory, input=self.token.get(), text=True).returncode,
        )


class BuffrsInstallTask(Task):
    """Install dependencies defined in `Proto.toml`"""

    description = "Runs `buffrs install` to download protobuf dependencies"
    buffrs_bin: Property[str] = Property.default("buffrs", help="The path to the buffrs binary.")

    def execute(self) -> TaskStatus:
        command = [self.buffrs_bin.get(), "install"]

        result = TaskStatus.from_exit_code(
            command,
            sp.call(command, cwd=self.project.directory),
        )

        if result.is_succeeded():
            # Create a .gitignore file in the proto/vendor directory to ensure it does not get committed.
            vendor_dir = self.project.directory / "proto" / "vendor"
            vendor_dir.mkdir(exist_ok=True, parents=True)
            vendor_dir.joinpath(".gitignore").write_text("*\n")

        return result


class BuffrsPublishTask(Task):
    """This task uses buffrs to publish a new release of the buffrs package.

    Requires at least Buffrs 0.8.0."""

    description = "Publish a buffrs package"

    registry: Property[str] = Property.required(
        help="The Artifactory URL to publish to (e.g. `https://<domain>/artifactory`)."
    )
    repository: Property[str] = Property.required(
        help="The Artifactory repository to publish to (this should be a Generic repository)."
    )
    version: Property[str | None] = Property.default(None, help="Override the version from the manifest.")
    buffrs_bin: Property[str] = Property.default("buffrs", help="The path to the buffrs binary.")

    def execute(self) -> TaskStatus:
        command = [
            self.buffrs_bin.get(),
            "publish",
            "--registry",
            self.registry.get(),
            "--repository",
            self.repository.get(),
            "--allow-dirty",
        ]
        if (version := self.version.get()) is not None:
            command += ["--set-version", version]
        self.logger.info("Running %s", command)
        return TaskStatus.from_exit_code(
            command,
            sp.call(command, cwd=self.project.directory),
        )
