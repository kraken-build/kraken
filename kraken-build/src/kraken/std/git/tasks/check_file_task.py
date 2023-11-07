from __future__ import annotations

import enum
import subprocess
from pathlib import Path
from typing import Literal

from kraken.core import Property, Task, TaskStatus
from kraken.core.system.task import TaskStatusType


def check_file_status(file_path: Path) -> CommitedFileStatus:
    file_path = file_path.absolute()
    if not file_path.exists():
        return CommitedFileStatus.MISSING
    ls_files = subprocess.run(
        ["git", "ls-files", "--", str(file_path)], capture_output=True, text=True, cwd=file_path.parent
    ).stdout.strip()
    if ls_files != file_path.name:
        return CommitedFileStatus.NOT_COMMITTED
    return CommitedFileStatus.COMMITED


class CommitedFileStatus(enum.Enum):
    """
    Represents the status of a file that is supposed to be commited.
    """

    COMMITED = enum.auto()
    NOT_COMMITTED = enum.auto()
    MISSING = enum.auto()

    def to_description(self, file_path: Path) -> str:
        match self:
            case CommitedFileStatus.COMMITED:
                return f"'{file_path}' exists and is committed"
            case CommitedFileStatus.NOT_COMMITTED:
                return f"'{file_path}' exists but is not committed"
            case CommitedFileStatus.MISSING:
                return f"'{file_path}' does not exist"
            case _:
                assert False


class CheckFileTask(Task):
    """
    This task checks if a file exists and is committed in a Git repository, or the inverse.
    """

    #: The path to the file to check. A relative path is considered relative to the project directory.
    file_to_check: Property[Path]

    #: The desired state of the file.
    state: Property[Literal["present", "absent"]] = Property.default("present")

    #: If set to True, the task will not fail if the file state does not match the desired state.
    #: Otherwise, the task will error.
    warn_only: Property[bool] = Property.default(False)

    def execute(self) -> TaskStatus:
        """Checks that a give file exists and has been committed to git."""
        status = check_file_status(self.project.directory / self.file_to_check.get())
        success: bool
        match status:
            case CommitedFileStatus.COMMITED:
                success = self.state.get() == "present"
            case CommitedFileStatus.NOT_COMMITTED | CommitedFileStatus.MISSING:
                success = self.state.get() != "present"
            case _:
                assert False, f"Unknown status: {status}"

        return TaskStatus(
            TaskStatusType.SUCCEEDED
            if success
            else (TaskStatusType.WARNING if self.warn_only.get() else TaskStatusType.FAILED),
            status.to_description(self.file_to_check.get()),
        )

    def get_description(self) -> str | None:
        if self.state.get() == "present":
            return f"Checks if the file '{self.file_to_check.get()}' is committed."
        else:
            return f"Checks if the file '{self.file_to_check.get()}' is not committed."
