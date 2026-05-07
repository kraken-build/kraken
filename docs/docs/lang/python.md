# Python

  [Kaniko]: https://github.com/GoogleContainerTools/kaniko
  [Buildx]: https://docs.docker.com/buildx/working-with-buildx/

Lint, format and test Python code.

__Supported tools__

* Mypy
* Pytest
* Ruff
* ty

__Supported build systems (for installing/building)__

* uv

## Build systems

A build system that is supported by Kraken is needed to use the {@pylink kraken.std.python.tasks.build_task.BuildTask}.
Most build systems will support managed Python environments for the current Python project (e.g. `uv sync` will
create a virtual environment and install the project into it).

Build systems implemented for Kraken will take care of the installation, ensuring that the Python package indexes
registered in the build script are made available to the installation process.

Kraken assumes that these package managers or build systems are installed locally by the user and accessible in the `$PATH`.
If you use a custom installation, make sure these tools are available in there.

## Publishing

Independent of the Python build system used, Kraken will use [`uv publish`] to publish to a Package index.

[`uv publish`]: https://docs.astral.sh/uv/guides/package/#publishing-your-package
