# Docker

  [Kaniko]: https://github.com/GoogleContainerTools/kaniko
  [Buildx]: https://docs.docker.com/buildx/working-with-buildx/

Build and publish Docker images.

__Supported backends__

* [x] Native Docker (currently does not perform auth for you)
* [x] [Buildx][] (currently does not perform auth for you)
* [x] [Kaniko][]

__Quickstart__

```py
# .kraken.py
from kraken.std.docker import build_docker_image

build_docker_image(
    name="buildDocker",
    dockerfile="docker/release.Dockerfile",
    tags=["kraken-example"],
    load=True,
)
```

__Integration tests__

The `build_docker_image()` function for Buildx and Kaniko are continuously integration tested to ensure that build
time secrets under `/run/secrets` don't appear in the final image.
