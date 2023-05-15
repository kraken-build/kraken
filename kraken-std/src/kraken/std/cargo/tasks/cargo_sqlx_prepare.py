from __future__ import annotations

from pathlib import Path

from kraken.core import Property, TaskStatus

from ._cargo_sqlx import CargoBaseSqlxTask


class CargoSqlxPrepareTask(CargoBaseSqlxTask):
    """Using cargo sqlx, generate the sqlx-data.json file for offline mode. If check=True, will verify that the
    sqlx-data.json file is up-to-date with the current database schema and code queries."""

    migrations: Property[Path]
    check: Property[bool] = Property.default(False)

    def execute(self) -> TaskStatus:
        arguments = ["prepare"]
        if self.check.get():
            arguments.append("--check")

        return self._execute_command(arguments)

    def get_description(self) -> str | None:
        if self.check.get():
            return "Check that sqlx-data.json file is up-to-date with the current database schema and code queries"
        return "Generate the sqlx-data.json file for offline mode"
