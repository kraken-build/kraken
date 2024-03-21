import hashlib
from pathlib import Path
from typing import cast

import httpx

from kraken.core.system.property import Property
from kraken.core.system.task import Task, TaskStatus


class FetchFileTask(Task):
    """Fetches a tarball from a URL and unpacks it. May also be used to fetch ZIP files."""

    url: Property[str] = Property.required(help="The URL to fetch the tarball from.")
    chmod: Property[int | None] = Property.default(None, help="The file mode to set on the downloaded file.")
    out: Property[Path] = Property.output(help="The path to the unpacked tarball.")

    # TODO(@niklas): SHA256 checksum verification

    # Task

    def prepare(self) -> TaskStatus | None:
        store_path = self.out.get()
        if store_path.exists():
            return TaskStatus.skipped(f"{store_path} already exists.")
        return None

    def execute(self) -> TaskStatus | None:
        store_path = self.out.get()
        url = self.url.get()

        print(f"Downloading {url} ...")

        with store_path.open("wb") as f:
            with httpx.stream("GET", url, follow_redirects=True, timeout=60) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    f.write(chunk)
            if (chmod := self.chmod.get()) is not None:
                store_path.chmod(chmod)

        return TaskStatus.succeeded(f"Fetched file from {url} to {store_path}.")


def fetch_file(*, name: str, url: str, chmod: int | None = None, suffix: str = "") -> FetchFileTask:
    """Fetches a tarball from a URL and unpacks it. May also be used to fetch ZIP files."""

    from kraken.build import context

    urlhash = hashlib.md5(url.encode()).hexdigest()
    dest = context.build_directory / ".store" / f"{urlhash}-{name}{suffix}"
    task_name = f"{name}-{urlhash}"

    if task_name in context.root_project.tasks():
        task = cast(FetchFileTask, context.root_project.task(task_name))
    else:
        task = context.root_project.task(task_name, FetchFileTask)
        task.url = url
        task.chmod = chmod
        task.out = dest

    return task
