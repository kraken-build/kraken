
from collections.abc import Sequence
from dataclasses import dataclass
import logging
from pathlib import Path
from kraken.common.supplier import Supplier
from kraken.core.system.project import Project
from kraken.core.system.task import Task
from kraken.std.buffrs import buffrs_install as buffrs_install_task
from kraken.std.protobuf import ProtocTask, buf
from kraken.std.python.tasks.pex_build_task import pex_build

logger = logging.getLogger(__name__)


def protobuf_project(
    *,
    buf_version: str = "1.30.0",
    buffrs_version: str = "0.8.0",
) -> "ProtobufProject":
    """ Defines tasks for a Protobuf project.

    * If a `Proto.toml` exists, [Buffrs][] will be be used to install dependencies. Buffrs will produce a `proto/vendor`
        directory that will be used as the source directory for the remaining Protobuf tasks. If the `Proto.toml` does
        not exist, the `proto` directory will be used as the source directory and no dependency management will be
        performed.
    * [Buf][] will be used to lint the Protobuf files (either `proto/vendor` excluding any Protobuf files that are
        vendored in through dependencies, or the `proto` folder if Buffrs is not used).

    The returned [kraken.build.protobuf.v1alpah1.ProtobufProject][] instance can be used to create a code generator
    for supported languages from the Protobuf files.

    Args:
        buf_version: The version of [Buf][] to install from GitHub releases.
        buffrs_version: The version of [Buffrs][] to install from GitHub releases.
    """

    from kraken.build import project

    if project.directory.joinpath("Proto.toml").is_file():
        logger.debug("[%s] Detected Proto.toml, using Buffrs for dependency management.", project)
        buffrs_install = buffrs_install_task()
        proto_dir = "proto/vendor"
    else:
        logger.debug("[%s] No Proto.toml detected, not using Buffrs for dependency management.", project)
        buffrs_install = None
        proto_dir = "proto"

    buf(
        buf_version=buf_version,
        path=proto_dir,
        dependencies=[buffrs_install] if buffrs_install else [],
    )

    return ProtobufProject(
        project=project,
        proto_dir=proto_dir,
        dependencies=[buffrs_install] if buffrs_install else [],
    )


@dataclass
class ProtobufProject:
    """ Represents a Protobuf project, and allows creating code generators for supported versions. """

    project: Project
    """ The Kraken project. """

    proto_dir: str
    """ The directory where the Protobuf files are located (relative to the project directory). """

    dependencies: Sequence[Task]
    """ A list of tasks that protobuf generation should depend on."""

    grpcio_tools_version_spec: str = ">=1.62.1,<2.0.0"
    """ The version of grpcio-tools to use. """

    mypy_protobuf_version_spec: str = ">=3.5.0,<4.0.0"
    """ The version of mypy-protobuf to use. """

    @property
    def protoc(self) -> Supplier[str]:
        """ Returns the ProtocTask for the project. """

        return pex_build(
            binary_name="protoc",
            requirements=[f"grpcio-tools{self.grpcio_tools_version_spec}", f"mypy-protobuf{self.mypy_protobuf_version_spec}"],
            entry_point="grpc_tools.protoc",
            venv="prepend",
        ).output_file.map(lambda p: str(p.absolute()))

    def python(self, source_dir: Path, ) -> tuple[Task, Supplier[Sequence[Path]]]:
        """ Create a code generator for Python code from the Protobuf files.

        The Python code will be generated in a `proto` namespace package that will be placed into your projects
        source directory. Before invoking the `protoc` compiler, the contents of the `proto` directory (the one
        that contains the Protobuf source code) will be copied and wrapped into a temporary `proto` parent directory
        to ensure that imports are generated correctly.

        Args:
            name: The name of the task to create.
            source_dir: The directory where Python source files should be generated.
        Returns:
            1. The task that generates the Python code.
            2. The supplier for the generated Python files that should be excluded from formatting checks and linting.
        """

        protoc = self.project.task("protoc.python", ProtocTask)
        protoc.protoc_bin = self.protoc
        protoc.proto_dir = self.proto_dir
        protoc.generate("python", Path(source_dir))
        protoc.generate("grpc_python", Path(source_dir))
        protoc.generate("mypy", Path(source_dir))
        protoc.generate("mypy_grpc", Path(source_dir))

        # TODO(@niklas): The `protoc` command seems to have a `pyi_out` option, but it only generates .pyi files for
        #   the Protobuf messages, not the gRPC stubs. Am I missing something? Until then, we keep using mypy-protobuf.
        # protoc.generate("pyi", Path(source_directory))

        protoc.depends_on(*self.dependencies)

        out_dir = self.project.directory / source_dir / "proto"
        out_files = Supplier.of_callable(
            lambda: [*out_dir.rglob("*.py"), *out_dir.rglob("*.pyi")],
            derived_from=[protoc.proto_dir],  # Just some property of the task ensure lineage
        )

        return (protoc, out_files)
