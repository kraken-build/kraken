from __future__ import annotations

from pathlib import Path

from kraken.common.path import try_relative_to
from kraken.common.strings import as_bytes
from kraken.common.supplier import Supplier
from kraken.core import Project, Property, Task, TaskStatus

from .check_file_contents_task import CheckFileContentsTask

DEFAULT_ENCODING = "utf-8"


class RenderFileTask(Task):
    """The RenderFileTask renders a single file to disk.

    The contents of the file can be provided by the :attr:`content` property or by creating a subclass
    that implements the :meth:`get_file_contents` method.

    It is common for a RenderFileTask to be added to the default `apply` task group. A matching check task,
    should you create it, would be a good candidate to add to the default `check` group.
    """

    description = 'Create or update "%(file)s".'

    file: Property[Path]
    content: Property[str | bytes]
    encoding: Property[str] = Property.default(DEFAULT_ENCODING)
    overwrite: Property[bool] = Property.default(True)

    def create_check(
        self,
        name: str = "{name}.check",
        task_class: type[CheckFileContentsTask] | None = None,
        description: str | None = None,
        group: str | None = "check",
    ) -> CheckFileContentsTask:
        task = self.project.task(
            name.replace("{name}", self.name), task_class or CheckFileContentsTask, description=description, group=group
        )
        task.file = self.file.value
        task.content = self.content.value
        task.encoding = self.encoding.value
        task.render_prepare = Supplier.of_callable(self.prepare)
        task.depends_on(self, mode="order-only")
        return task

    # Task

    def prepare(self) -> TaskStatus:
        file = self.file.get()
        if not self.overwrite.get() and file.exists():
            return TaskStatus.skipped(f"{file} already exists")
        if file.is_file() and file.read_bytes() == as_bytes(self.content.get(), self.encoding.get()):
            return TaskStatus.up_to_date(f'"{try_relative_to(file)}" is up to date')
        return TaskStatus.pending()

    def execute(self) -> TaskStatus:
        file = self.file.get()
        file.parent.mkdir(exist_ok=True, parents=True)
        content = as_bytes(self.content.get(), self.encoding.get())
        file.write_bytes(content)
        return TaskStatus.succeeded(f"wrote {len(content)} bytes to {try_relative_to(file)}")


def render_file(
    name: str,
    description: str | None = None,
    group: str | None = "apply",
    create_check: bool = True,
    check_name: str = "{name}.check",
    check_group: str | None = "check",
    check_description: str | None = None,
    project: Project | None = None,
    task_class: type[RenderFileTask] | None = None,
    check_task_class: type[CheckFileContentsTask] | None = None,
    *,
    file: str | Path | Supplier[Path],
    content: str | Supplier[str],
    encoding: str | Supplier[str] = DEFAULT_ENCODING,
    overwrite: bool | Supplier[bool] = True,
) -> tuple[RenderFileTask, CheckFileContentsTask | None]:
    project = project or Project.current()
    render_task = project.task(name, task_class or RenderFileTask, description=description, group=group)
    render_task.file = Path(file) if isinstance(file, str) else file
    render_task.content = content
    render_task.encoding = encoding
    render_task.overwrite = overwrite

    if create_check:
        check_task = render_task.create_check(
            check_name.replace("{name}", name), check_task_class, description=check_description, group=check_group
        )
    else:
        check_task = None

    return render_task, check_task
