from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import tomli
import tomli_w

from kraken.core import Project, Property
from kraken.std.util.render_file_task import RenderFileTask

from ..config import CargoRegistry


class CargoSyncConfigTask(RenderFileTask):
    """This task updates the `.cargo/config.toml` file to inject configuration values."""

    file: Property[Path]

    #: If enabled, the configuration file will be replaced rather than updated.
    replace: Property[bool] = Property.default(False)

    #: The global-credential-providers to set in the config. If not set, the config won't be touched. The providers
    #: must be specified in reverse order of precedence. Read more about credential providers here:
    #: https://doc.rust-lang.org/cargo/reference/registry-authentication.html
    global_credential_providers: Property[Sequence[str]] = Property.default(["cargo:token"])

    #: The registries to insert into the configuration.
    registries: Property[list[CargoRegistry]] = Property.default_factory(list)

    #: Enable fetching Cargo indexes with the Git CLI.
    git_fetch_with_cli: Property[bool]

    #: Whether to use the sparse protocol for crates.io.
    crates_io_protocol: Property[Literal["git", "sparse"]] = Property.default("sparse")

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.file.setcallable(lambda: project.directory / ".cargo" / "config.toml")
        self.content.setcallable(lambda: self.get_file_contents(self.file.get()))

    def get_file_contents(self, file: Path) -> str | bytes:
        content = tomli.loads(file.read_text()) if not self.replace.get() and file.exists() else {}
        if self.global_credential_providers.is_set():
            if self.global_credential_providers.get() is None:
                content.setdefault("registry", {}).pop("global-credential-providers", None)
            else:
                content.setdefault("registry", {})["global-credential-providers"] = list(
                    self.global_credential_providers.get()
                )
        content.setdefault("registries", {})["crates-io"] = {"protocol": self.crates_io_protocol.get()}
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
