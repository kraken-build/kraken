# ::krakenw-root

from kraken.common import buildscript

buildscript(requirements=["kraken-build>=0.45.1"])

from kraken.build import project  # noqa: E402
from kraken.std.docker import build_docker_image  # noqa: E402
from kraken.std.util.render_file_task import RenderFileTask  # noqa: E402

dockerfile = project.task("dockerfile", RenderFileTask)
dockerfile.content.set("FROM ubuntu:focal\nRUN echo Hello world\n")
dockerfile.file.set(project.build_directory / "Dockerfile")

build = build_docker_image(
    name="buildDocker",
    dockerfile=dockerfile.file,
    tags=["kraken-example"],
    load=True,
)
