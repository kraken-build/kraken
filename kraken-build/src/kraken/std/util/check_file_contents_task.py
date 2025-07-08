from __future__ import annotations

from difflib import Differ
from pathlib import Path

from kraken.common import colored
from kraken.common.path import try_relative_to
from kraken.common.strings import as_string
from kraken.core import Property, Task, TaskStatus


class CheckFileContentsTask(Task):
    """The CheckFileContentsTask will compare the contents of a file of a file with the content specified in the
    :attr:`content` property and error if it does not match. This is usually used in combination with a
    :class:`RenderFileTask`."""

    description = 'Check if "%(file)s" is up to date.'

    file: Property[Path]
    content: Property[str | bytes]
    encoding: Property[str]
    render_prepare: Property[TaskStatus]
    update_task_name: Property[str | None] = Property.default(None)
    show_diff: Property[bool] = Property.default(True)

    def _show_diff(self, a: str, b: str) -> None:
        differ = Differ()
        for line in differ.compare(a.splitlines(keepends=True), b.splitlines(keepends=True)):
            print(line, end="")

    # Task

    def prepare(self) -> TaskStatus:
        return self.render_prepare.get()

    def execute(self) -> TaskStatus | None:
        file = try_relative_to(self.project.directory / self.file.get())
        file_fmt = colored(str(file), "yellow", attrs=["bold"])

        if update_task_name := self.update_task_name.get():
            uptask = colored(update_task_name, "blue", attrs=["bold"])
            message_suffix = f", run {uptask} to generate it"
        else:
            message_suffix = ""

        if not file.exists():
            return TaskStatus.failed(f'file "{file_fmt}" does not exist{message_suffix}')
        if not file.is_file():
            return TaskStatus.failed(f'"{file}" is not a file')

        encoding = self.encoding.get()
        if (file_content := file.read_text(encoding)) != (content := as_string(self.content.get(), encoding)):
            if self.show_diff.get():
                self._show_diff(file_content, content)
            return TaskStatus.failed(f'file "{file_fmt}" is not up to date{message_suffix}')

        return TaskStatus.succeeded(f'file "{file_fmt}" is up to date')
