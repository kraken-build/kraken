from kraken.common import buildscript
buildscript(additional_sys_paths=["."])

from kraken.build import project
from my_tasks import WriteDockerfileTask, DockerBuildTask

writeDockerfile = project.task("writeDockerfile", WriteDockerfileTask)
writeDockerfile.content = "FROM ubuntu:latest\nRUN echo Hello World"

dockerBuild = project.task("dockerBuild", DockerBuildTask)
dockerBuild.dockerfile = writeDockerfile.dockerfile

project.subproject("sub")
