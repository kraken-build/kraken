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


## Sidecar Containers

Sidecar containers are containers that are run alongside other tasks, and can stay active in the background the entire
time. The development workflow or integration tests of your project may require that certain Docker containers run in
the background, such as a database or a web server. Kraken provides a way to run these containers alongside your tasks
using the {@pylink kraken.std.docker.sidecar_container} function.

```py
from kraken.std.docker import sidecar_container
from kraken.std.python import pytest

sidecar_container(
    name="postgres",
    image="postgres:latest",
    ports=["5432:5432"],
    env={"POSTGRES_PASSWORD": "postgres"},
)

pytest(tests_dir="src").depends_on("postgres.start")
```

This example will start a Postgres container before running the tests. The `depends_on` argument ensures that the
Postgres container is started before the tests are run. The `start` suffix is added to the task name. The function
will also generate a `postgres.stop` task that you can run to stop the container via the CLI.

```
$ kraken run :postgres.start

Start build

> :postgres.start PENDING
1d3e0c9d2ccf5f60f82f179e1340fbfaaeda398c0ee0167b34cd8b9ee6ba51ac
> :postgres.start SUCCEEDED (Container kraken.sidecar-container.postgres started)

Build summary

  :postgres.start SUCCEEDED (Container kraken.sidecar-container.postgres started) [0.866s]

> docker ps
CONTAINER ID   IMAGE             COMMAND                  CREATED          STATUS          PORTS                    NAMES
e40cc9fc9ff3   postgres:latest   "docker-entrypoint.s…"   14 seconds ago   Up 13 seconds   0.0.0.0:5432->5432/tcp   kraken.sidecar-container.postgres
```

---

## API Documentation

@pydoc kraken.std.docker.build_docker_image

@pydoc kraken.std.docker.sidecar_container

@pydoc kraken.std.docker.tasks.base_build_task.BaseBuildTask

### Native

@pydoc kraken.std.docker.tasks.native_build_task.NativeBuildTask

### Buildx

@pydoc kraken.std.docker.tasks.buildx_build_task.BuildxBuildTask

### Kaniko

@pydoc kraken.std.docker.tasks.kaniko_build_task.KanikoBuildTask

### Manifest Tool

@pydoc kraken.std.docker.manifest_tool.ManifestToolPushTask
