from __future__ import annotations

from kraken.core import Property

from .cargo_build_task import CargoBuildTask


class CargoClippyTask(CargoBuildTask):
    """Runs `cargo clippy` for linting or applying suggestions."""

    workspace: Property[bool] = Property.default(True)
    all_features: Property[bool] = Property.default(True)
    fix: Property[bool] = Property.default(False)
    allow: Property[str | None] = Property.default("staged")
    deny_warnings: Property[bool] = Property.default(False)

    # CargoBuildTask

    def get_cargo_command(self, env: dict[str, str]) -> list[str]:
        command = ["cargo", "clippy"]
        if self.workspace.get():
            command += ["--workspace"]
        if self.all_features.get():
            command += ["--all-features"]
        if self.fix.get():
            command += ["--fix"]
            allow = self.allow.get()
            if allow == "staged":
                command += ["--allow-staged"]
            elif allow == "dirty":
                command += ["--allow-dirty", "--allow-staged"]
            elif allow is not None:
                raise ValueError(f"invalid allow: {allow!r}")
        # must be last, as this argument it passed to cargo check
        if self.deny_warnings.get():
            command += ["--", "-D warnings"]
        return command
