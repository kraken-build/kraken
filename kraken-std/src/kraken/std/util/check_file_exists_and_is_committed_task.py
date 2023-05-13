from __future__ import annotations

import enum
import subprocess
from pathlib import Path

from kraken.core.api import Project, Property, Task, TaskStatus


class CheckFileExistsAndIsCommittedError(enum.Enum):
    DOES_NOT_EXIST = 1
    IS_NOT_COMMITTED = 2

    def to_description(self, file_path: Path) -> str:
        if self == CheckFileExistsAndIsCommittedError.DOES_NOT_EXIST:
            return f"'{file_path}' does not exist"

        if self == CheckFileExistsAndIsCommittedError.IS_NOT_COMMITTED:
            return f"'{file_path}' exists but is not committed"

        return "IMPOSSIBLE STATE"


class CheckFileExistsAndIsCommittedTask(Task):
    file_to_check: Property[Path]

    def _check(self) -> CheckFileExistsAndIsCommittedError | None:
        file_to_check = self.project.directory.absolute() / self.file_to_check.get()
        if not file_to_check.exists():
            return CheckFileExistsAndIsCommittedError.DOES_NOT_EXIST
        elif subprocess.getoutput(f"git ls-files -- {file_to_check}") != file_to_check.name:
            return CheckFileExistsAndIsCommittedError.IS_NOT_COMMITTED

        return None

    def execute(self) -> TaskStatus:
        """Checks that a give file exists and has been committed to git."""
        check_error = self._check()
        if check_error:
            return TaskStatus.failed(check_error.to_description(self.file_to_check.get()))

        return TaskStatus.succeeded()

    def get_description(self) -> str | None:
        return f"Check file '{self.file_to_check.get()}' exists and is committed"


def check_file_exists_and_is_committed(path: Path, project: Project | None = None) -> CheckFileExistsAndIsCommittedTask:
    project = project or Project.current()
    return project.do(
        f"checkFileExistsAndIsCommitted/{path}",
        CheckFileExistsAndIsCommittedTask,
        group="check",
        file_to_check=path,
    )
