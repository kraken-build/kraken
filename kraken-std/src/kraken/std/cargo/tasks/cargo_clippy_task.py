from __future__ import annotations

from kraken.core import Property

from .cargo_build_task import CargoBuildTask


class CargoClippyTask(CargoBuildTask):
    """Runs `cargo clippy` for linting or applying suggestions."""

    fix: Property[bool] = Property.default(False)
    allow: Property[str | None] = Property.default("staged")

    # CargoBuildTask

    def get_cargo_command(self, env: dict[str, str]) -> list[str]:
        command = ["cargo", "clippy"]
        if self.fix.get():
            command += ["--fix"]
            allow = self.allow.get()
            if allow == "staged":
                command += ["--allow-staged"]
            elif allow == "dirty":
                command += ["--allow-dirty", "--allow-staged"]
            elif allow is not None:
                raise ValueError(f"invalid allow: {allow!r}")
        return command
