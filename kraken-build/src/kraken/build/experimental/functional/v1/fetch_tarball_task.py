import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Literal, cast

import httpx

from kraken.core.system.property import Property
from kraken.core.system.task import Task, TaskStatus


class FetchTarballTask(Task):
    """Fetches a tarball from a URL and unpacks it. May also be used to fetch ZIP files."""

    url: Property[str] = Property.required(help="The URL to fetch the tarball from.")
    format: Property[Literal["tar", "zip"] | None] = Property.default(
        "tar", help="The format of the tarball. If not set, will be inferred from the file extension in the URL."
    )
    out: Property[Path] = Property.output(help="The path to the unpacked tarball.")

    # TODO(@niklas): SHA256 checksum verification

    def _unpack(self, archive: Path, store_path: Path) -> None:
        """Unpacks the archive at the given path to the store path."""

        if (format_ := self.format.get()) is None:
            format_ = "zip" if archive.suffix == ".zip" else "tar"

        shutil.unpack_archive(archive, store_path, format_)

    # Task

    def prepare(self) -> TaskStatus | None:
        store_path = self.out.get()
        if store_path.exists():
            return TaskStatus.skipped(f"{store_path} already exists.")
        return None

    def execute(self) -> TaskStatus | None:

        print(f"Downloading {self.url.get()} ...")
        with tempfile.TemporaryDirectory() as tmp, Path(tmp).joinpath("archive").open("wb") as f:
            with httpx.stream("GET", self.url.get(), follow_redirects=True, timeout=60) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    f.write(chunk)

            store_path = self.out.get()
            print(f"Unpacking to {store_path} ...")
            self._unpack(Path(tmp) / "archive", store_path)

        return TaskStatus.succeeded(f"Fetched tarball from {self.url.get()} to {store_path}.")


def fetch_tarball(*, name: str, url: str, format: Literal["tar", "zip"] | None = None) -> FetchTarballTask:
    """Fetches a tarball from a URL and unpacks it. May also be used to fetch ZIP files."""

    from kraken.build import context

    urlhash = hashlib.md5(url.encode()).hexdigest()
    dest = context.build_directory / ".store" / f"{urlhash}-{name}"
    task_name = f"{name}-{urlhash}"

    if task_name in context.root_project.tasks():
        task = cast(FetchTarballTask, context.root_project.task(task_name))
    else:
        task = context.root_project.task(task_name, FetchTarballTask)
        task.url = url
        task.format = format
        task.out = dest

    return task
