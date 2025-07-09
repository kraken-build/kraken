from pathlib import Path
from typing import Literal, Sequence

from kraken.core import BuildCache, Property, Task
from kraken.core.system.task import TaskStatus

from .python import PYTHON_PLATFORMS, BuildPythonLambdaZip, PythonPlatform


class BuildPythonLambdaZipTask(Task):
    outfile: Property[Path] = Property.output()
    project_directory: Property[Path | None]
    include: Property[Sequence[Path]]
    packages: Property[Sequence[str]]
    requirements: Property[Path | None]
    platform: Property[PythonPlatform | None]
    quiet: Property[bool]

    def execute(self) -> TaskStatus | None:
        inputs = BuildPythonLambdaZip(
            project_directory=self.project_directory.get_or(None),
            include=self.include.get_or([]),
            packages=self.packages.get_or([]),
            requirements=self.requirements.get_or(None),
            platform=self.platform.get_or(None),
            quiet=self.quiet.get_or(False),
        )

        with BuildCache.for_(self) as cache:
            cache.consumes(inputs)
            if inputs.project_directory:
                cache.consumes_path(inputs.project_directory)
            for path in inputs.include:
                cache.consumes_path(path)
            cache.finalize()

            outfile = "lambda.zip"
            cache.link_result(outfile, self.outfile.get())

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
    packages: Sequence[str] = (),
    requirements: str | Path | None = None,
    platform: PythonPlatform | None = None,
    quiet: bool = False,
) -> BuildPythonLambdaZipTask:
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
    task.packages = list(packages)
    task.requirements = project.directory / requirements if requirements else None
    task.platform = platform
    task.quiet = quiet

    return task
