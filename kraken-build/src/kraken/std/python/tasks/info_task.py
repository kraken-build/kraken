import subprocess
from pathlib import Path

from kraken.common import colored
from kraken.core import Project, Property, Task, TaskStatus
from kraken.std.python.settings import python_settings

from ..buildsystem import PythonBuildSystem


class InfoTask(Task):
    build_system: Property[PythonBuildSystem]

    def get_description(self) -> str:
        return "Displays metadata about the Kraken-managed environment."

    def execute(self) -> TaskStatus:
        """Displays metadata about the Kraken-managed environment."""
        python_path = self.get_python_path()
        virtual_env_path = self.get_virtual_env_path()
        try:
            version = self.get_python_version()
        except subprocess.CalledProcessError as error:
            return TaskStatus.failed(f"Error while getting the version of the current Python interpreter: {error}")

        print(
            colored(f" ---------- {self.build_system.get().name}-managed environment information ----------", "magenta")
        )
        print(colored("Python version:           ", "cyan"), colored(f"{version.strip()}", "blue"))
        print(colored("Python path:              ", "cyan"), colored(f"{python_path}", "blue"))
        print(colored("Virtual environment path: ", "cyan"), colored(f"{virtual_env_path}", "blue"))
        print(colored(" ------------------------------------------------------------", "magenta"))

        return TaskStatus.succeeded()

    def get_virtual_env_path(self) -> Path:
        """
        Returns the current virtual environment path
        """
        return self.build_system.get().get_managed_environment().get_path()

    def get_python_path(self) -> Path:
        """Returns the path of the Python interpreter of the Kraken-managed environment."""
        return self.get_virtual_env_path() / "bin" / "python"

    def get_python_version(self) -> str:
        """Returns the version of the Python interpreter of the Kraken-managed environment."""
        return subprocess.run(
            [self.get_python_path(), "--version"], stdout=subprocess.PIPE, shell=False, check=True
        ).stdout.decode("utf-8")


def info(*, project: Project | None = None, build_system: PythonBuildSystem | None = None) -> InfoTask:
    """
    This task displays a list of useful info on current Python and virtual environment settings.
    """

    project = project or Project.current()
    if build_system is None:
        build_system = python_settings().build_system

    task = project.task("python.info", InfoTask)
    task.build_system = build_system
    return task
