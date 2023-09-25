from __future__ import annotations

import contextlib
import logging
import os
import subprocess as sp
from urllib.parse import urljoin

from kraken.common import CredentialsWithHost, atomic_file_swap
from kraken.core import BackgroundTask, Project, Property, Task, TaskStatus

from .manifest import BuffrsManifest

logger = logging.getLogger(__name__)


class BuffrsLoginTask(Task):
    """This task logs into artifactory with buffrs"""

    description = "Login to artifactory with buffrs."
    artifactory_credentials: Property[CredentialsWithHost]

    def execute(self) -> TaskStatus:
        credentials = self.artifactory_credentials.get()
        url = urljoin(credentials.host, "/artifactory")

        command = ["buffrs", "login", "--registry", url]

        return TaskStatus.from_exit_code(
            command,
            sp.run(
                command,
                cwd=self.project.directory,
                env=os.environ.copy(),
                input=credentials.password,
                text=True,
            ).returncode,
        )


class BuffrsInstallTask(Task):
    """Install dependencies defined in `Proto.toml`"""

    description = "Runs `buffrs install` to download protobuf dependencies"

    def execute(self) -> TaskStatus:
        command = ["buffrs", "install"]

        return TaskStatus.from_exit_code(
            command,
            sp.call(
                command,
                cwd=self.project.directory,
                env=os.environ.copy(),
            ),
        )


class BuffrsBumpVersionTask(BackgroundTask):
    """This task bumps the version numbers in `Proto.toml`"""

    description = 'Bump the version in `Proto.toml` to "%(version)"'
    version: Property[str]

    def _get_updated_proto_toml(self) -> str:
        project = self.project or Project.current()

        manifest = BuffrsManifest.read(project.directory / "Proto.toml")

        if manifest.package is None:
            return manifest.to_toml_string()

        manifest.package.version = self.version.get().format()

        return manifest.to_toml_string()

    def start_background_task(self, exit_stack: contextlib.ExitStack) -> TaskStatus | None:
        project = self.project or Project.current()
        content = self._get_updated_proto_toml()

        fp = exit_stack.enter_context(atomic_file_swap(project.directory / "Proto.toml", "w", always_revert=True))
        fp.write(content)
        fp.close()

        version = self.version.get()

        return TaskStatus.started(f"temporarily bump to {version.format()}")


class BuffrsPublishTask(Task):
    """This task uses buffrs to publish a new release of the buffrs package."""

    description = "Publish a buffrs package"
    artifactory_repository: Property[str]

    def execute(self) -> TaskStatus:
        command = ["buffrs", "publish", "--repository", self.artifactory_repository.get(), "--allow-dirty"]

        return TaskStatus.from_exit_code(
            command,
            sp.call(
                command,
                cwd=self.project.directory,
                env=os.environ.copy(),
            ),
        )
