from __future__ import annotations

from kraken.core import Project, Property, Task, TaskStatus

from ..settings import PythonSettings, python_settings


class LoginTask(Task):
    settings: Property[PythonSettings]

    def prepare(self) -> TaskStatus | None:
        settings = self.settings.get()
        if not settings.build_system:
            return TaskStatus.skipped("no build system configured")
        if not settings.build_system.requires_login():
            return TaskStatus.skipped("build system requires no log in")
        return TaskStatus.pending()

    def execute(self) -> None:
        settings = self.settings.get()
        assert settings.build_system is not None
        settings.build_system.login(settings)


def login(*, name: str = "python.login", project: Project | None = None) -> LoginTask:
    project = project or Project.current()
    task = project.task(name, LoginTask)
    task.settings = python_settings(project)
    return task
