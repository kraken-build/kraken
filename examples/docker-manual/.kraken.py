## ::krakenw-root

from kraken.common import buildscript

buildscript(
    requirements=["kraken-build @ ../../kraken-wrapper"], additional_sys_paths=["."]
)

from kraken.build import project  # noqa: E402
from my_tasks import DockerBuildTask, WriteDockerfileTask  # noqa: E402

writeDockerfile = project.task("writeDockerfile", WriteDockerfileTask)
writeDockerfile.content = "FROM ubuntu:latest\nRUN echo Hello World"

dockerBuild = project.task("dockerBuild", DockerBuildTask)
dockerBuild.dockerfile = writeDockerfile.dockerfile

project.subproject("sub")
