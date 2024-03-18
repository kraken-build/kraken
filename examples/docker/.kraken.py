from kraken.core import Project

from kraken.std.docker import build_docker_image
from kraken.std.generic.render_file import RenderFileTask

project = Project.current()

dockerfile = project.task("dockerfile", RenderFileTask)
dockerfile.content.set("FROM ubuntu:focal\nRUN echo Hello world\n")
dockerfile.file.set(project.build_directory / "Dockerfile"),

build = build_docker_image(
    name="buildDocker",
    dockerfile=dockerfile.file,
    tags=["kraken-example"],
    load=True,
)
