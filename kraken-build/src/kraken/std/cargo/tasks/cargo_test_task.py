from enum import Enum, auto

from kraken.core import Property

from .cargo_build_task import CargoBuildTask


class CargoTestIgnored(Enum):
    """How to treat ignored tests"""

    #: Skip ignored tests
    SKIP = auto()

    #: Run ignored tests
    INCLUDE = auto()

    #: Run only ignored tests
    ONLY = auto()


class CargoTestTask(CargoBuildTask):
    """This task runs `cargo test` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    description = "Run `cargo test`."

    #: When set to a list of filters, run only tests which match any of these filters.
    filter: Property[list[str]] = Property.default_factory(list)

    #: Specify how to treat ignored tests, by default they are skipped.
    ignored: Property[CargoTestIgnored] = Property.default(CargoTestIgnored.SKIP)

    def get_cargo_command(self, env: dict[str, str]) -> list[str]:
        command = super().get_cargo_subcommand(env, "test")
        command.append("--")

        match self.ignored.get():
            case CargoTestIgnored.SKIP:
                pass
            case CargoTestIgnored.INCLUDE:
                command.append("--include-ignored")
            case CargoTestIgnored.ONLY:
                command.append("--ignored")

        for filter in self.filter.get():
            command.append(filter)

        return command
