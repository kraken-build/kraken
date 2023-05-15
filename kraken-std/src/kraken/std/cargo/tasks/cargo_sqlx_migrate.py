from __future__ import annotations

from pathlib import Path

from kraken.core import Property, TaskStatus

from ._cargo_sqlx import CargoBaseSqlxTask


class CargoSqlxMigrateTask(CargoBaseSqlxTask):
    """Apply SQL migrations using cargo sqlx. If the database URL is not provided, it will default to the environment
    variable DATABASE_URL. If the database does not exist, it will be created."""

    migrations: Property[Path]

    def execute(self) -> TaskStatus:
        result = self.db_create()
        if result.is_not_ok():
            return result

        result = self.migrate_run()
        if result.is_not_ok():
            return result

        return TaskStatus.succeeded()

    def db_create(self) -> TaskStatus:
        return self._execute_command(["db", "create"])

    def migrate_run(self) -> TaskStatus:
        arguments = ["migrate", "run"]
        if self.migrations.is_filled():
            arguments.extend(["--source", str(self.migrations.get().absolute())])

        return self._execute_command(arguments)

    def get_description(self) -> str | None:
        return "Apply SQL migrations using cargo sqlx"
