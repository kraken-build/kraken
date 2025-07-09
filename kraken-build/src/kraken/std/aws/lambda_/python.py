import argparse
import logging
import os
import shutil
import subprocess
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, Sequence

from uv import find_uv_bin

logger = logging.getLogger(__name__)

PythonPlatform = Literal[
    "windows",
    "linux",
    "macos",
    "x86_64-pc-windows-msvc",
    "i686-pc-windows-msvc",
    "x86_64-unknown-linux-gnu",
    "aarch64-apple-darwin",
    "x86_64-apple-darwin",
    "aarch64-unknown-linux-gnu",
    "aarch64-unknown-linux-musl",
    "x86_64-unknown-linux-musl",
    "x86_64-manylinux2014",
    "x86_64-manylinux_2_17",
    "x86_64-manylinux_2_28",
    "x86_64-manylinux_2_31",
    "x86_64-manylinux_2_32",
    "x86_64-manylinux_2_33",
    "x86_64-manylinux_2_34",
    "x86_64-manylinux_2_35",
    "x86_64-manylinux_2_36",
    "x86_64-manylinux_2_37",
    "x86_64-manylinux_2_38",
    "x86_64-manylinux_2_39",
    "x86_64-manylinux_2_40",
    "aarch64-manylinux2014",
    "aarch64-manylinux_2_17",
    "aarch64-manylinux_2_28",
    "aarch64-manylinux_2_31",
    "aarch64-manylinux_2_32",
    "aarch64-manylinux_2_33",
    "aarch64-manylinux_2_34",
    "aarch64-manylinux_2_35",
    "aarch64-manylinux_2_36",
    "aarch64-manylinux_2_37",
    "aarch64-manylinux_2_38",
    "aarch64-manylinux_2_39",
    "aarch64-manylinux_2_40",
    "wasm32-pyodide2024",
]


UV_BIN = os.fsdecode(os.getenv("KRAKEN_UV_BIN", find_uv_bin()))
PYTHON_PLATFORMS: set[str] = set(PythonPlatform.__args__)  # type: ignore[attr-defined]


@dataclass(frozen=True)
class BuildPythonLambdaZip:
    project_directory: Path | None = None
    include: Sequence[Path] = ()
    packages: Sequence[str] = ()
    requirements: Path | None = None
    platform: PythonPlatform | None = None
    uv_bin: Path = Path(UV_BIN)
    quiet: bool = False

    def build(self, outfile: Path, build_directory: Path | None = None) -> None:
        """Shorthand to calling :func:`build_python_lambda_zip` with the inputs from this dataclass."""

        build_python_lambda_zip(
            uv_bin=self.uv_bin,
            outfile=outfile,
            project_directory=self.project_directory,
            include=self.include,
            packages=self.packages,
            requirements=self.requirements,
            platform=self.platform,
            build_directory=build_directory,
            quiet=self.quiet,
        )


def build_python_lambda_zip(
    uv_bin: Path,
    outfile: Path,
    project_directory: Path | None = None,
    include: Sequence[Path] = (),
    packages: Sequence[str] = (),
    requirements: Path | None = None,
    platform: PythonPlatform | None = None,
    build_directory: Path | None = None,
    quiet: bool = False,
    managed_python: bool = True,
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
                *(["--managed-python"] if managed_python else []),
                *(["-q"] if quiet else []),
                "--target",
                os.fspath(build_directory),
                *(["--python-platform", platform] if platform else []),
                *(["-r", os.fspath(requirements)] if requirements else []),
                "--",
                *packages,
                *([os.fspath(project_directory.absolute())] if project_directory else []),
            ]
            if not quiet:
                if platform:
                    print(f"uv pip install (for platform '{platform}') → {build_directory}/")
                else:
                    print(f"uv pip install → {build_directory}/")
            logger.debug(f"Running command: {' '.join(command)}")
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
        type=Path,
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
        uv_bin=Path(UV_BIN),
    )


if __name__ == "__main__":
    main()
