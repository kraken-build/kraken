from pathlib import Path
from typing import Literal, Sequence

from kraken.core import BuildCache, Property, Task
from kraken.core.system.task import TaskStatus

from .python import PYTHON_PLATFORMS, BuildPythonLambdaZip, Include, PythonPlatform


class BuildPythonLambdaZipTask(Task):
    outfile: Property[Path] = Property.output()
    project_directory: Property[Path | None]
    include: Property[Sequence[Path]]
    include_data: Property[Sequence[Include]]
    packages: Property[Sequence[str]]
    requirements: Property[Path | None]
    python_version: Property[str]
    platform: Property[PythonPlatform | None]
    quiet: Property[bool]
    symlink_result: Property[bool] = Property.default(
        True,
        help="Whether to symlink the resulting ZIP archive to `outfile`. If disabled, the file will be copied instead.",
    )

    def execute(self) -> TaskStatus | None:
        include = [
            *map(Include.coerce, self.include.get_or([])),
            *self.include_data.get_or([]),
        ]

        inputs = BuildPythonLambdaZip(
            project_directory=self.project_directory.get_or(None),
            include=include,
            packages=self.packages.get_or([]),
            requirements=self.requirements.get_or(None),
            python_version=self.python_version.get_or(None),
            platform=self.platform.get_or(None),
            quiet=self.quiet.get_or(False),
        )

        with BuildCache.for_(self) as cache:
            cache.consumes(inputs)
            if inputs.project_directory:
                cache.consumes_path(inputs.project_directory)
            for item in inputs.include:
                cache.consumes_path(item.source)
            cache.finalize()

            outfile = "lambda.zip"
            if self.symlink_result.get():
                cache.link_result(outfile, self.outfile.get())
            else:
                cache.copy_result(outfile, self.outfile.get())

            if cache.exists():
                return TaskStatus.skipped(f"retained {self.outfile.get()}")
            else:
                build_directory = cache.staging_path() / "build"
                inputs.build(cache.staging_path() / outfile, build_directory)
                cache.commit()
                return TaskStatus.succeeded(f"built {self.outfile.get()}")


def python_lambda_zip(
    name: str,
    outfile: str | Path | None = None,
    project_directory: Path | None | Literal["ignore"] = None,
    include: Sequence[str | Path] = (),
    include_data: Sequence[str | Include] = (),
    packages: Sequence[str] = (),
    requirements: str | Path | None = None,
    python_version: str | None = None,
    platform: PythonPlatform | None = None,
    quiet: bool = False,
    symlink_result: bool = True,
) -> BuildPythonLambdaZipTask:
    """
    Create a task to build a Python AWS Lambda deployment package.

    Args:
        name: The name of the task.
        outfile: The output file path for the ZIP archive. If not specified,
                 the archive will be placed in the build directory with the name
                 "{name}.zip".
        project_directory: The path to the Python project directory. If set to
                           "ignore", the project directory will not be included.
                           If None and a project configuration file is found in
                           the current directory, that directory will be used.
        include: A sequence of files or directories to include in the ZIP archive.
                Each item can be a string in the format "source:dest" or just
                "source" (which will use the basename as the destination).
        include_data: A sequence of paths with an optional rename to include in
                      the ZIP archive. Each item can be an Include object or a
                      string in the format "source:dest".
        packages: A sequence of Python packages to install in the Lambda
                  environment.
        requirements: A path to a requirements file containing Python packages
                     to install.
        python_version: The Python version to use for the Lambda function.
        platform: The target platform for the Lambda function.
        quiet: If True, suppress output from the build process.
        symlink_result: If True, symlink the resulting ZIP archive to the
                       specified outfile. If False, copy the file instead.

    Returns:
        A task that, when executed, builds the Python Lambda deployment package.

    Raises:
        ValueError: If an invalid platform is specified.
    """
    from kraken.build import project

    if project_directory == "ignore":
        project_directory = None
    elif project_directory is None:
        if (
            project.directory.joinpath("pyproject.toml").exists()
            or project.directory.joinpath("setup.cfg").exists()
            or project.directory.joinpath("setup.py").exists()
        ):
            project_directory = project.directory

    if platform and platform not in PYTHON_PLATFORMS:
        raise ValueError(f"invalid `platform`, got {platform!r}, expected one of {PYTHON_PLATFORMS}")

    task = project.task(name, BuildPythonLambdaZipTask)
    task.outfile = project.directory / outfile if outfile else project.build_directory / f"{name}.zip"
    task.project_directory = project_directory
    task.include = [project.directory / x for x in include]
    task.include_data = [Include(project.directory / i.source, i.dest) for i in map(Include.coerce, include_data)]
    task.packages = list(packages)
    task.requirements = project.directory / requirements if requirements else None
    task.python_version = python_version
    task.platform = platform
    task.quiet = quiet
    task.symlink_result = symlink_result

    return task
