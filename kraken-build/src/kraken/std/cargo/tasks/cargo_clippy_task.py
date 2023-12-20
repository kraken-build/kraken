from __future__ import annotations

from kraken.core import Property

from .cargo_build_task import CargoBuildTask


class CargoClippyTask(CargoBuildTask):
    """Runs `cargo clippy` for linting or applying suggestions."""

    #: When set to True, tells clippy to fix the issues.
    fix: Property[bool] = Property.default(False)

    #: When running Clippy in Fix mode, allow a dirty or staged Git work tree.
    allow: Property[str | None] = Property.default("staged")

    def get_cargo_command(self, env: dict[str, str]) -> list[str]:
        command = super().get_cargo_subcommand(env, "clippy")
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
