from __future__ import annotations

from pathlib import Path

from kraken.core import Property, TaskStatus

from ._cargo_sqlx import CargoBaseSqlxTask


class CargoSqlxPrepareTask(CargoBaseSqlxTask):
    """Generate sqlx's query-*.json files for offline mode using sqlx-cli. If check=True, verify that the query-*.json
    files are up-to-date with the current database schema and code queries."""

    migrations: Property[Path]
    check: Property[bool] = Property.default(False)

    def execute(self) -> TaskStatus:
        arguments = ["prepare"]
        if self.check.get():
            arguments.append("--check")

        return self._execute_command(arguments)

    def get_description(self) -> str | None:
        if self.check.get():
            return "Check that query-*.json files are up-to-date with the current database schema and code queries"
        return "Generate the query-*.json files for offline mode"
