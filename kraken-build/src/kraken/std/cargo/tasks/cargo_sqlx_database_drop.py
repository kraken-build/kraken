from __future__ import annotations

from kraken.core import TaskStatus

from ._cargo_sqlx import CargoBaseSqlxTask


class CargoSqlxDatabaseDropTask(CargoBaseSqlxTask):
    """Drop a database using sqlx-cli."""

    description = "Drop a database using sqlx-cli"

    def execute(self) -> TaskStatus:
        return self._execute_command(["database", "drop"])
