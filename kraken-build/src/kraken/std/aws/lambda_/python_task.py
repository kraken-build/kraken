from pathlib import Path
from typing import Literal, Sequence

from kraken.core import Property, Task
from kraken.core.system.task import TaskStatus

from .python import build_python_lambda_zip as _build_python_lambda_zip


class BuildPythonLambdaZipTask(Task):
    outfile: Property[Path]
    project_directory: Property[Path | None]
    include: Property[Sequence[Path]]
    packages: Property[Sequence[str]]
    requirements: Property[Path | None]
    quiet: Property[bool]

    # TODO: implement prepare() to check if we need to rebuild from scratch?

    def execute(self) -> TaskStatus | None:
        _build_python_lambda_zip(
            outfile=self.outfile.get(),
            project_directory=self.project_directory.get_or(None),
            include=self.include.get_or([]),
            packages=self.packages.get_or([]),
            requirements=self.requirements.get_or(None),
            quiet=self.quiet.get_or(False),
        )

        return TaskStatus.succeeded(f"built {self.outfile.get()}")


def python_lambda_zip(
    name: str,
    outfile: str | Path | None = None,
    project_directory: Path | None | Literal["ignore"] = None,
    include: Sequence[str | Path] = (),
    packages: Sequence[str] = (),
    requirements: str | Path | None = None,
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

    task = project.task(name, BuildPythonLambdaZipTask)
    task.outfile = project.directory / outfile if outfile else project.build_directory / f"{name}.zip"
    task.project_directory = project_directory
    task.include = [project.directory / x for x in include]
    task.packages = list(packages)
    task.requirements = project.directory / requirements if requirements else None
    task.quiet = quiet

    return task
