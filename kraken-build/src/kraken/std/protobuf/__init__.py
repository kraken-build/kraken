""" Lint and format Protobuf files with `buf`. Requires that `buf` is preinstalled. """

from __future__ import annotations

import platform as _platform
import subprocess as sp
from collections.abc import Sequence
from pathlib import Path
from shutil import rmtree

from kraken.build.utils.v1alpha1 import fetch_file, fetch_tarball, shell_cmd, write_file
from kraken.common.supplier import Supplier
from kraken.core import Property, Task, TaskStatus


class ProtocTask(Task):
    """Generate code with `protoc`."""

    protoc_bin: Property[str] = Property.default("protoc", help="Path to `protoc` binary.")
    proto_dir: Property[Path | str] = Property.required(help="The directories containing the .proto files.")
    generators: Property[Sequence[tuple[str, Path]]] = Property.required(
        help="The code generators to use. Each tuple contains the language name and the output directory."
    )
    create_gitignore: Property[bool] = Property.default(True, help="Create a .gitignore file in the output directory.")

    def generate(self, language: str, output_dir: Path) -> None:
        """Helper to specify a code generator.

        IMPORTANT: The contents of *output_dir* will be deleted before running `protoc`."""

        self.generators.setdefault(())
        self.generators.setmap(lambda v: [*v, (language, output_dir)])

    def execute(self) -> TaskStatus | None:

        # TODO: Re-organize proto_dir to be prefixed with a `proto/` directory that is not contained
        #       in the `--proto_path` argument. This is necessary to ensure we generate imports in
        #       a `proto/` namespace package.

        command = [self.protoc_bin.get()]
        command += [f"--proto_path={self.project.directory / self.proto_dir.get()}"]
        for language, output_dir in self.generators.get():
            rmtree(output_dir, ignore_errors=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            if self.create_gitignore.get():
                output_dir.joinpath(".gitignore").write_text("*\n")
            command += [f"--{language}_out={output_dir}"]
        command += [str(p) for p in Path(self.project.directory).rglob("*.proto")]

        return TaskStatus.from_exit_code(
            command,
            sp.call(command, cwd=self.project.directory),
        )


def get_buf_binary(version: str, target_triplet: str | None = None) -> Supplier[Path]:
    """Fetches the `buf` binary from GitHub."""

    target_triplet = target_triplet or get_buf_triplet()

    if "Windows" in target_triplet:
        url = f"https://github.com/bufbuild/buf/releases/download/v{version}/buf-{target_triplet}.exe"
        return fetch_file(name="buf", url=url, chmod=0o777, suffix=".exe").out.map(lambda p: p.absolute())
    else:
        url = f"https://github.com/bufbuild/buf/releases/download/v{version}/buf-{target_triplet}.tar.gz"
        return fetch_tarball(name="buf", url=url).out.map(lambda p: p.absolute() / "buf" / "bin" / "buf")


def get_buf_triplet() -> str:
    match (_platform.machine(), _platform.system()):
        case (machine, "Linux"):
            return f"Linux-{machine}"
        case (machine, "Darwin"):
            return f"Darwin-{machine}"
        case ("AMD64", "Windows"):
            return "Windows-x86_64"
        case other:
            raise NotImplementedError(f"Platform {other} is not supported by `buf`.")


def buf(
    *,
    buf_version: str = "1.30.0",
    path: str = "proto",
    exclude_path: Sequence[str] = (),
    dependencies: Sequence[Task] = (),
) -> tuple[Task, Task]:
    from shlex import quote

    buf_bin = get_buf_binary(buf_version).map(str)

    # Configure buf; see https://buf.build/docs/lint/rules
    buf_config = write_file(
        name="buf.yaml",
        content_dedent="""
        version: v1
        lint:
            use:
                - DEFAULT
            except:
                - PACKAGE_VERSION_SUFFIX
                # NOTE(@niklas): We only ignore this rule because Buffrs uses hyphens in place of underscores for
                #       the generated directories, but the `package` directive in Protobuf can't contain hyphens.
                - PACKAGE_DIRECTORY_MATCH
    """,
    ).map(str)

    exclude_args = " ".join(f"--exclude-path {quote(path)}" for path in exclude_path)

    buf_format = shell_cmd(
        name="buf.format",
        template='"{buf}" format -w --config "{config}" "{path}" {exclude_args}',
        buf=buf_bin,
        path=path,
        config=buf_config,
        exclude_args=exclude_args,
    )
    buf_format.depends_on(*dependencies)

    buf_lint = shell_cmd(
        name="buf.lint",
        template='"{buf}" lint --config "{config}" "{path}" {exclude_args}',
        buf=buf_bin,
        path=path,
        config=buf_config,
        exclude_args=exclude_args,
    )
    buf_lint.depends_on(*dependencies)

    return (buf_format, buf_lint)
