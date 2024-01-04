from __future__ import annotations

from pathlib import Path

from kraken.core import Property, TaskStatus

from ._cargo_sqlx import CargoBaseSqlxTask


class CargoSqlxMigrateTask(CargoBaseSqlxTask):
    """Apply SQL migrations using sqlx-cli."""

    description = "Apply SQL migrations using sqlx-cli"
    migrations: Property[Path]

    def execute(self) -> TaskStatus:
        arguments = ["migrate", "run"]
        if self.migrations.is_filled():
            arguments.extend(["--source", str(self.migrations.get().absolute())])

        return self._execute_command(arguments)
