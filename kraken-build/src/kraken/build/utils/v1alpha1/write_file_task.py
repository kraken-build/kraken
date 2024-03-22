import hashlib
from pathlib import Path
from textwrap import dedent

from kraken.common.supplier import Supplier
from kraken.core.system.property import Property
from kraken.core.system.task import Task, TaskStatus


class WriteFile(Task):
    """Fetches a file from a URL."""

    content: Property[str] = Property.required(help="The content of the file.")
    out: Property[Path] = Property.output(help="The path to the output file.")

    # Task

    def prepare(self) -> TaskStatus | None:
        store_path = self.out.get()
        if store_path.exists() and store_path.read_text() == self.content.get():
            return TaskStatus.skipped(f"{store_path} already exists.")
        return None

    def execute(self) -> TaskStatus | None:
        store_path = self.out.get()
        content = self.content.get()
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text(content)
        return TaskStatus.succeeded(f"Wrote {len(content)} {store_path}")


def write_file(
    *, name: str, content: str | Supplier[str] | None = None, content_dedent: str | Supplier[str] | None = None
) -> Supplier[Path]:
    """Writes a file to the store.

    NOTE: Because task names must be known before hand but the content hash can only be known at a later time, the
    task name is fixed as specified with *name* and thus may conflict if the same name is reused.
    """

    from kraken.build import context

    if content_dedent is not None:
        content = Supplier.of(content_dedent).map(dedent)
    elif content is not None:
        content = Supplier.of(content)
    else:
        raise ValueError("Either content or content_dedent must be set.")

    store_dir = context.build_directory / ".store"
    dest = content.map(lambda c: hashlib.md5(c.encode()).hexdigest()).map(lambda h: store_dir / f"{h}-{name}")

    task = context.root_project.task(name, WriteFile)
    task.content = content
    task.out = dest
    return task.out
