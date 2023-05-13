import subprocess
from pathlib import Path

from kraken.core import Project, Property, Task


class WriteDockerfileTask(Task):
    content: Property[str]  #: The content of the Dockerfile.
    dockerfile: Property[Path]  #: The output file to write the Dockerfile to.

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.dockerfile.set(self.project.build_directory / "Dockerfile")

    def execute(self) -> None:
        dockerfile = self.dockerfile.get()
        dockerfile.parent.mkdir(parents=True, exist_ok=True)
        dockerfile.write_text(self.content.get())


class DockerBuildTask(Task):
    context: Property[Path]  #: The build context.
    dockerfile: Property[Path]  #: The dockerfile.

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.context.set(project.directory)
        project.group("build").add(self)

    def execute(self) -> None:
        command = ["docker", "build", str(self.context.get())]
        dockerfile = self.dockerfile.get_or(None)
        if dockerfile is not None:
            command += ["-f", str(dockerfile)]
        subprocess.check_call(command)
