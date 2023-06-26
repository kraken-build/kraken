from __future__ import annotations

from pathlib import Path

from kraken.common.path import try_relative_to
from kraken.common.strings import as_bytes
from kraken.core import Property, Task, TaskStatus
from termcolor import colored


class CheckFileContentsTask(Task):
    """The CheckFileContentsTask will compare the contents of a file of a file with the content specified in the
    :attr:`content` property and error if it does not match. This is usually used in combination with a
    :class:`RenderFileTask`."""

    description = 'Check if "%(file)s" is up to date.'

    file: Property[Path]
    content: Property[str | bytes]
    encoding: Property[str]
    update_task_name: Property[str]
    render_prepare: Property[TaskStatus]

    # Task

    def prepare(self) -> TaskStatus:
        return self.render_prepare.get()

    def execute(self) -> TaskStatus | None:
        file = try_relative_to(self.file.get())
        file_fmt = colored(str(file), "yellow", attrs=["bold"])

        if self.update_task_name.is_filled():
            uptask = colored(self.update_task_name.get(), "blue", attrs=["bold"])
            message_suffix = f", run {uptask} to generate it"
        else:
            message_suffix = ""

        if not file.exists():
            return TaskStatus.failed(f'file "{file_fmt}" does not exist{message_suffix}')
        if not file.is_file():
            return TaskStatus.failed(f'"{file}" is not a file')
        if file.read_bytes() != as_bytes(self.content.get(), self.encoding.get()):
            return TaskStatus.failed(f'file "{file_fmt}" is not up to date{message_suffix}')
        return TaskStatus.succeeded(f'file "{file_fmt}" is up to date')
