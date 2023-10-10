from __future__ import annotations

import enum
import logging
import os
import subprocess as sp

from kraken.common import CredentialsWithHost, atomic_file_swap
from kraken.core import Project, Property, Task, TaskStatus

from .manifest import BuffrsManifest

logger = logging.getLogger(__name__)


class Language(enum.Enum):
    PYTHON = "python"


class BuffrsLoginTask(Task):
    """This task logs into artifactory with buffrs"""

    description = "Login to artifactory with buffrs."
    artifactory_credentials: Property[CredentialsWithHost]

    def execute(self) -> TaskStatus:
        credentials = self.artifactory_credentials.get()

        command = ["buffrs", "login", "--registry", credentials.host]

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


class BuffrsPublishTask(Task):
    """This task uses buffrs to publish a new release of the buffrs package."""

    description = "Publish a buffrs package"
    artifactory_repository: Property[str]
    version: Property[str]

    def _get_updated_proto_toml(self) -> str:
        project = self.project or Project.current()

        manifest = BuffrsManifest.read(project.directory / "Proto.toml")

        if manifest.package is None:
            return manifest.to_toml_string()

        manifest.package.version = self.version.get().format()

        return manifest.to_toml_string()

    def execute(self) -> TaskStatus:
        command = ["buffrs", "publish", "--repository", self.artifactory_repository.get(), "--allow-dirty"]
        project = self.project
        content = self._get_updated_proto_toml()

        with atomic_file_swap(project.directory / "Proto.toml", "w", always_revert=True) as atomic_file:
            atomic_file.write(content)
            atomic_file.close()

            version = self.version.get()
            logger.info(f"temporarily bumped Proto.toml to {version.format()}")

            return TaskStatus.from_exit_code(
                command,
                sp.call(
                    command,
                    cwd=self.project.directory,
                    env=os.environ.copy(),
                ),
            )


class BuffrsGenerateTask(Task):
    """This task uses buffrs to generate code definitions for installed packages."""

    description = "Generates code for installed package with buffrs"
    language: Property[Language]
    generated_output_dir: Property[str]

    def execute(self) -> TaskStatus:
        command = [
            "buffrs",
            "generate",
            "--lang",
            self.language.get().value,
            "--out-dir",
            self.generated_output_dir.get(),
        ]

        return TaskStatus.from_exit_code(
            command,
            sp.call(
                command,
                cwd=self.project.directory,
                env=os.environ.copy(),
            ),
        )
