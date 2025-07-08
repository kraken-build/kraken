from __future__ import annotations

import logging
import os
import shutil
import subprocess as sp
import sys
from collections.abc import Iterable, MutableMapping

from kraken.common.pyenv import VirtualEnvInfo, get_current_venv
from kraken.core import Project, Task, TaskRelationship, TaskStatus
from kraken.std.python.buildsystem import ManagedEnvironment

from ..settings import python_settings

logger = logging.getLogger(__name__)


class EnvironmentAwareDispatchTask(Task):
    """Base class for tasks that run a subcommand. The command ensures that the command is aware of the
    environment configured in the project settings."""

    python_dependencies: list[str] = []
    """Packages that should be installed for this task to run."""

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.settings = python_settings(project)

    def get_relationships(self) -> Iterable[TaskRelationship]:
        from .install_task import InstallTask

        # If a python.install task exists, we may need it.
        for task in (t for t in self.project.tasks().values() if isinstance(t, InstallTask)):
            yield TaskRelationship(task, True, False)

        yield from super().get_relationships()

    def get_execute_command_v2(self, env: MutableMapping[str, str]) -> list[str] | TaskStatus:
        raise NotImplementedError()

    def handle_exit_code(self, code: int) -> TaskStatus:
        return TaskStatus.from_exit_code(None, code)

    def activate_managed_environment(self, venv: ManagedEnvironment, environ: MutableMapping[str, str]) -> None:
        active_venv = get_current_venv(environ)
        if active_venv is None or self.settings.always_use_managed_env:
            if not venv.exists():
                logger.warning("Managed environment (%s) does not exist", venv)
                return
            managed_env = VirtualEnvInfo(venv.get_path())
            logger.info("Activating managed environment (%s)", managed_env.path)
            managed_env.activate(environ)
        elif active_venv:
            logger.info("An active virtual environment was found, not activating managed environment")

    def execute(self) -> TaskStatus:
        env = os.environ.copy()
        command = self.get_execute_command_v2(env)
        if isinstance(command, TaskStatus):
            return command
        if self.settings.build_system and self.settings.build_system.supports_managed_environments():
            self.activate_managed_environment(self.settings.build_system.get_managed_environment(), env)
        if self.python_dependencies and shutil.which(command[0], path=env.get("PATH")) is None:
            logger.warning("Some Python dependencies of %s are not installed.", self.name)
            logger.warning("To run this task successfully you should add to the `pyproject.toml` file:")
            logger.warning("[tool.poetry.group.dev.dependencies]")
            for dep in self.python_dependencies:
                logger.warning('%s = "*"', dep)
            return TaskStatus.failed("The %s dependencies are missing" % self.python_dependencies)
        logger.info("%s", command)
        shell = sys.platform.startswith("win32")  # Windows requires shell to find executable in path
        result = sp.call(command, cwd=self.project.directory, env=env, shell=shell)
        return self.handle_exit_code(result)
