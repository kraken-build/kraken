from __future__ import annotations

from pathlib import Path

from kraken.core import Project, Property, TaskStatus
from kraken.std.python.buildsystem import PythonBuildSystem
from kraken.std.util.render_file_task import RenderFileTask

from ..pyproject import Pyproject
from ..settings import PythonSettings, python_settings


class UpdatePyprojectTask(RenderFileTask):
    """Updates the `pyproject.toml` to ensure certain configuration options are set."""

    build_system: Property[PythonBuildSystem]
    settings: Property[PythonSettings]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.content.setcallable(lambda: self.get_file_contents(self.file.get()))

    def get_file_contents(self, file: Path) -> str:
        pyproject = Pyproject.read(file)
        settings = self.settings.get()
        assert settings.build_system
        settings.build_system.update_pyproject(settings, pyproject)
        return pyproject.to_toml_string()

    def prepare(self) -> TaskStatus:
        settings = self.settings.get()
        if not settings.build_system:
            return TaskStatus.skipped("no build system")
        return super().prepare()


def update_pyproject_task(
    *,
    name: str = "pyproject.update",
    group: str = "apply",
    project: Project | None = None,
) -> UpdatePyprojectTask:
    project = project or Project.current()
    task = project.task(name, UpdatePyprojectTask, group=group)
    task.settings = python_settings(project)
    task.file = project.directory / "pyproject.toml"
    task.create_check()
    return task
