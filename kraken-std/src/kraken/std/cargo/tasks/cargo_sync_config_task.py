from __future__ import annotations

from pathlib import Path
from typing import List

import tomli
import tomli_w
from kraken.core.api import Project, Property
from kraken.core.lib.render_file_task import RenderFileTask

from ..config import CargoRegistry


class CargoSyncConfigTask(RenderFileTask):
    """This task updates the `.cargo/config.toml` file to inject configuration values."""

    file: Property[Path]

    #: If enabled, the configuration file will be replaced rather than updated.
    replace: Property[bool] = Property.config(default=False)

    #: The registries to insert into the configuration.
    registries: Property[List[CargoRegistry]] = Property.config(default_factory=list)

    #: Enable fetching Cargo indexes with the Git CLI.
    git_fetch_with_cli: Property[bool]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.file.setcallable(lambda: project.directory / ".cargo" / "config.toml")
        self.content.setcallable(lambda: self.get_file_contents(self.file.get()))

    def get_file_contents(self, file: Path) -> str | bytes:
        content = tomli.loads(file.read_text()) if not self.replace.get() and file.exists() else {}
        for registry in self.registries.get():
            content.setdefault("registries", {})[registry.alias] = {"index": registry.index}
        if self.git_fetch_with_cli.is_filled():
            if self.git_fetch_with_cli.get():
                content.setdefault("net", {})["git-fetch-with-cli"] = True
            else:
                if "net" in content:
                    content["net"].pop("git-fetch-with-cli", None)
        lines = []
        if self.replace.get():
            lines.append("# This file is managed by Kraken. Manual edits to this file will be overwritten.")
        else:
            lines.append(
                "# This file is partially managed by Kraken. Comments and manually added "
                "repositories are not preserved."
            )
        lines.append(tomli_w.dumps(content))
        return "\n".join(lines)
