import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from hashlib import md5
from pathlib import Path
from posixpath import basename
from shutil import copyfileobj
from tarfile import open as TarFile

from requests import get

from kraken.common import not_none
from kraken.core import Property, Task, TaskStatus


class ShellcheckTask(Task):
    """Lint one or more Shell scripts with Shellcheck. It can install Shellcheck for you at build time on
    Linux (arm64, amd64) and OSX (amd64). On other systems, you need to install Shellcheck separately. On OSX,
    you can install it with Homebrew: `brew install shellcheck`."""

    version: Property[str] = Property.default("0.9.0")
    url: Property[str | None] = Property.default(None)
    files: Property[Sequence[str | Path]]
    skip_on_not_installed: Property[bool] = Property.default(False)

    def get_download_url(self) -> str:
        if (url := self.url.get()) is not None:
            return url

        version = self.version.get()
        match (sys.platform, platform.machine()):
            case ("linux", "arm64") | ("linux", "x86_64") | ("darwin", "x86_64"):
                arch_alias = {"x86_64": "x86_64", "arm64": "aarch64"}[platform.machine()]
                url = (
                    "https://github.com/koalaman/shellcheck/releases/download/"
                    f"v{version}/shellcheck-v{version}.{sys.platform}.{arch_alias}.tar.xz"
                )
            case _:
                raise ValueError(
                    f"cannot install shellcheck for platform {sys.platform}-{platform.machine()}, install it yourself"
                )

        return url

    def install_shellcheck_from_url(self, url: str) -> str:
        md5sum = md5(url.encode()).hexdigest()
        store_path = self.project.context.build_directory / ".store" / md5sum
        archive_path = store_path / basename(url)
        bin_path = store_path / "shellcheck"

        if not bin_path.exists():
            if not archive_path.exists():
                store_path.mkdir(parents=True, exist_ok=True)
                self.logger.info("Downloading %s ...", url)
                try:
                    with archive_path.open("wb") as fp:
                        for chunk in get(url, stream=True).iter_content():
                            fp.write(chunk)
                except Exception:
                    archive_path.unlink()
                    raise
            self.logger.info("Extracting `%s` from %s ...", bin_path.name, archive_path)
            with TarFile(archive_path, "r") as tfp:
                member = next(m for m in tfp.getmembers() if basename(m.name) == "shellcheck")
                with not_none(tfp.extractfile(member)) as src, bin_path.open("wb") as dst:
                    copyfileobj(src, dst)
                bin_path.chmod(0o777)

        return str(bin_path.absolute())

    def execute(self) -> TaskStatus:
        try:
            url = self.get_download_url()
        except ValueError as exc:
            bin_path = "shellcheck"
            if not shutil.which(bin_path):
                status = TaskStatus.skipped if self.skip_on_not_installed.get() else TaskStatus.failed
                return status(str(exc))
        else:
            bin_path = self.install_shellcheck_from_url(url)

        command = [bin_path, *map(str, self.files.get())]
        return TaskStatus.from_exit_code(
            command,
            subprocess.run(command, cwd=self.project.directory).returncode,
        )


def shellcheck(*, name: str = "shellcheck", group: str = "lint", files: Sequence[str]) -> ShellcheckTask:
    """Create a task to lint the given *files*."""

    from kraken.build import project

    task = project.task(name, ShellcheckTask, group=group)
    task.files = files
    return task
