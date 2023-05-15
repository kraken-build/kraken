from __future__ import annotations

import subprocess as sp
from typing import List, Sequence

from kraken.core import Project, Property, Task, TaskStatus

RELEASE_URL = (
    "https://github.com/estesp/manifest-tool/releases/download/v{VERSION}/binaries-manifest-tool-{VERSION}.tar.gz"
)

# TODO (@NiklasRosenstein): Use existing manifest tool if it exists.
# TODO (@NiklasRosenstein): Ensure manifest-tool has credentials to push to the target


class ManifestToolPushTask(Task):
    """A task that uses `manifest-tool` to combine multiple container images from different platforms into a single
    multi-platform manifest.

    For more information on `manifest-tool`, check out the GitHub repository:

    https://github.com/estesp/manifest-tool/
    """

    #: The Docker platforms to create the manifest for.
    platforms: Property[List[str]]

    #: A Docker image tag that should contain the variables `OS`, `ARCH` and `VARIANT`.
    template: Property[str]

    #: The image ID to push the Docker image to.
    target: Property[str]

    def execute(self) -> TaskStatus:
        command = [
            "manifest-tool",
            "push",
            "from-args",
            "--platforms",
            ",".join(self.platforms.get()),
            "--template",
            self.template.get(),
            "--target",
            self.target.get(),
        ]
        self.logger.info("%s", command)
        result = sp.call(command)
        return TaskStatus.from_exit_code(command, result)


def manifest_tool(
    *,
    name: str,
    template: str,
    platforms: Sequence[str],
    target: str,
    inputs: Sequence[Task],
    group: str | None = None,
    project: Project | None = None,
) -> ManifestToolPushTask:
    project = Project.current()
    task = project.do(name, ManifestToolPushTask, group=group, template=template, target=target, platforms=platforms)
    task.add_relationship(inputs)
    return task
