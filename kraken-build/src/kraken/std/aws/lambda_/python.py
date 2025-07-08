import argparse
import os
import shutil
import subprocess
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from uv import find_uv_bin

UV_BIN = os.fsdecode(os.getenv("KRAKEN_UV_BIN", find_uv_bin()))


@dataclass
class PythonLambdaBuilder:
    """
    Build a lambda package from a Python project using Uv.
    """

    build_directory: Path
    """ The path where the lambda will be built before being packaged into a ZIP file. """

    handler: str = "lambda_function.lambda_handler"
    """ The name of the handler to specify when creating the lambda. """

    uv_bin: Path = Path(UV_BIN)
    """ Path to the Uv binary to use. """

    @dataclass
    class ModuleHandler:
        """Reference a lambda handler from an installed Python module or package."""

        module: str
        name: str

    @dataclass
    class ScriptHandler:
        """Reference a lambda handler from a script."""

        path: Path
        name: str

    Handler = ScriptHandler | ModuleHandler

    def build(
        self,
        *,
        entrypoint: Handler,
        requirements: Sequence[str] = (),
        requirements_file: Path | None = None,
    ) -> None:
        handler_file, handler_func = self.handler.split(".")
        entry_file = self.build_directory / f"{handler_file}.py"

        command = [
            os.fspath(self.uv_bin),
            "pip",
            "install",
            "--no-config",
            "--exact",
            "--target",
            os.fspath(self.build_directory),
        ]
        if requirements_file:
            command += ["-r", os.fspath(requirements_file)]
        command += [*requirements]
        subprocess.check_call(command)

        match entrypoint:
            case PythonLambdaBuilder.ScriptHandler():
                # TODO: Parse the script and check if the entrypoint.name is defined in the script?
                entry_file.write_text(entrypoint.path.read_text() + f"\n\n{handler_func} = {entrypoint.name}")
            case PythonLambdaBuilder.ModuleHandler():
                entry_file.write_text(f"from {entrypoint.module} import {entrypoint.name} as {handler_func}\n")
            case _:
                raise TypeError(f"Unexpected entrypoint: {entrypoint!r}")

    def package(self, output_file: Path) -> None:
        assert output_file.suffix == ".zip", output_file
        shutil.make_archive(
            os.fspath(output_file.parent / output_file.stem), format="zip", root_dir=self.build_directory
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--func", metavar="MODULE:FUNC", help="A function to run as the entrypoint.")
    parser.add_argument("--file", metavar="FILE:FUNC", help="A file to run as the entrypoint.")
    parser.add_argument("-r", "--requirements-file", metavar="FILE", type=Path)
    parser.add_argument(
        "-b",
        "--build-dir",
        help="Build directory. If not specified, a temporary directory will be used and deleted after.",
    )
    parser.add_argument("-o", "--outfile", metavar="FILE", help="Output ZIP file.", required=True, type=Path)
    parser.add_argument(
        "requirements",
        nargs="*",
    )

    args = parser.parse_args()

    with ExitStack() as stack:
        if not args.build_dir:
            args.build_dir = stack.enter_context(TemporaryDirectory())

        builder = PythonLambdaBuilder(
            build_directory=Path(args.build_dir),
        )

        if args.func:
            module, function = args.func.split(":")
            entrypoint: PythonLambdaBuilder.Handler = PythonLambdaBuilder.ModuleHandler(module, function)
        elif args.file:
            script, function = args.file.split(":")
            entrypoint = PythonLambdaBuilder.ScriptHandler(Path(script), function)
        else:
            parser.error("Need one of --script, --func or --file")

        builder.build(
            entrypoint=entrypoint,
            requirements=args.requirements,
            requirements_file=args.requirements_file,
        )

        builder.package(args.outfile)


if __name__ == "__main__":
    main()
