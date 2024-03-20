""" Lint and format Protobuf files with `buf`. Requires that `buf` is preinstalled. """

from __future__ import annotations

import subprocess as sp
import sys
from collections.abc import Sequence
from pathlib import Path
from platform import machine
from shutil import rmtree

import httpx

from kraken.core import Property, Task, TaskStatus


class BufInstallTask(Task):
    """Installs [buf](https://github.com/bufbuild/buf) from GitHub."""

    description = "Install buf."
    version: Property[str] = Property.default("1.30.0", help="The version of `buf` to install.")
    output_file: Property[Path] = Property.output(help="The path to the installed `buf` binary.")

    def _get_dist_url(self) -> str:
        version = self.version.get()
        suffix = ""
        match sys.platform:
            case "linux":
                platform = "Linux"
            case "darwin":
                platform = "Darwin"
            case "win32":
                platform = "Windows"
                suffix = ".exe"
            case _:
                raise NotImplementedError(f"Platform {sys.platform} is not supported by `buf`.")
        match machine():
            case "x86_64":
                arch = "x86_64"
            case "aarch64":
                arch = "aarch64" if platform == "Linux" else "arm64"
            case _:
                raise NotImplementedError(f"Architecture {machine()} is not supported by `buf`.")
        return f"https://github.com/bufbuild/buf/releases/download/v{version}/buf-{platform}-{arch}{suffix}"

    def _get_output_file(self) -> Path:
        filename = f"buf-v{self.version.get()}{'.exe' if sys.platform == 'win32' else ''}"
        return self.project.context.build_directory / filename

    def prepare(self) -> TaskStatus | None:
        if self._get_output_file().is_file():
            return TaskStatus.skipped("buf is already installed.")
        return None

    def execute(self) -> TaskStatus | None:
        dist_url = self._get_dist_url()
        output_file = self._get_output_file()
        output_file.parent.mkdir(parents=True, exist_ok=True)

        response = httpx.get(dist_url, timeout=10, follow_redirects=True)
        response = response.raise_for_status()
        output_file.write_bytes(response.content)

        self.output_file = output_file
        return TaskStatus.succeeded(f"Installed buf to {output_file}.")


class BufFormatTask(Task):
    """Format Protobuf files with `buf`."""

    description = "Format Protobuf files with buf."
    buf_bin: Property[str] = Property.default("buf", help="Path to `buf` binary.")

    def execute(self) -> TaskStatus | None:
        command = [self.buf_bin.get(), "format", "-w"]
        result = sp.call(command, cwd=self.project.directory / "proto")

        return TaskStatus.from_exit_code(command, result)


class BufLintTask(Task):
    """Lint Protobuf files with `buf`."""

    description = "Lint Protobuf files with buf."
    buf_bin: Property[str] = Property.default("buf", help="Path to `buf` binary.")

    def execute(self) -> TaskStatus | None:
        command = [self.buf_bin.get(), "lint"]
        result = sp.call(command, cwd=self.project.directory / "proto")

        return TaskStatus.from_exit_code(command, result)


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
