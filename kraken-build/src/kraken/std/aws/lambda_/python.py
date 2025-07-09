import argparse
import os
import shutil
import subprocess
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from uv import find_uv_bin

UV_BIN = os.fsdecode(os.getenv("KRAKEN_UV_BIN", find_uv_bin()))


def build_python_lambda_zip(
    outfile: Path,
    project_directory: Path | None = None,
    include: Sequence[Path] = (),
    packages: Sequence[str] = (),
    requirements: Path | None = None,
    build_directory: Path | None = None,
    uv_bin: Path | None = None,
    quiet: bool = False,
) -> None:
    uv_bin = uv_bin or Path(UV_BIN)

    with ExitStack() as stack:
        if build_directory is None:
            build_directory = Path(stack.enter_context(TemporaryDirectory()))
        else:
            build_directory.mkdir(parents=True, exist_ok=True)

        if requirements or packages or project_directory:
            command = [
                os.fspath(uv_bin),
                "pip",
                "install",
                "--no-config",
                "--exact",
                *(["-q"] if quiet else []),
                "--target",
                os.fspath(build_directory),
                *(["-r", os.fspath(requirements)] if requirements else []),
                "--",
                *packages,
                *([os.fspath(project_directory.absolute())] if project_directory else []),
            ]
            if not quiet:
                print(f"uv pip install → {build_directory}/")
            subprocess.check_call(command)

        for path in include:
            if not quiet:
                print(f"copy {path} → {build_directory}/")
            shutil.copy(path, build_directory)

        if not quiet:
            print(f"zip {build_directory}/ → {outfile}")
        shutil.make_archive(os.fspath(outfile.parent / outfile.stem), format="zip", root_dir=build_directory)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--python-project",
        metavar="PATH",
        help="Path to a Python project to install into the package.",
        type=Path,
    )
    parser.add_argument(
        "-i",
        "--include",
        default=[],
        action="append",
        help="A file to include at the top-level of the package.",
    )
    parser.add_argument(
        "-r",
        "--requirements",
        metavar="FILE",
        type=Path,
        help="A requirements file to install packages from.",
    )
    parser.add_argument(
        "-b",
        "--build-directory",
        help="Build directory. If not specified, a temporary directory will be used and deleted after.",
    )
    parser.add_argument(
        "-o",
        "--outfile",
        metavar="FILE",
        required=True,
        type=Path,
        help="Path of the output file. Should end with .zip",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "packages",
        nargs="*",
    )

    args = parser.parse_args()

    build_python_lambda_zip(
        outfile=args.outfile,
        project_directory=args.python_project,
        include=args.include,
        packages=args.packages,
        requirements=args.requirements,
        build_directory=args.build_directory,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    main()
