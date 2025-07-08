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

    def execute(self) -> TaskStatus:
        command = ["buffrs", "login", "--registry", self.registry.get()]
        return TaskStatus.from_exit_code(
            command,
            sp.run(command, cwd=self.project.directory, input=self.token.get(), text=True).returncode,
        )


class BuffrsInstallTask(Task):
    """Install dependencies defined in `Proto.toml`"""

    description = "Runs `buffrs install` to download protobuf dependencies"

    def execute(self) -> TaskStatus:
        command = ["buffrs", "install"]
        return TaskStatus.from_exit_code(
            command,
            sp.call(command, cwd=self.project.directory),
        )


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

    def execute(self) -> TaskStatus:
        command = [
            "buffrs",
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
