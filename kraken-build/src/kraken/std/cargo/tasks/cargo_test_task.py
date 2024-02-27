from .cargo_build_task import CargoBuildTask


class CargoTestTask(CargoBuildTask):
    """This task runs `cargo test` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    description = "Run `cargo test`."

    def get_cargo_command(self, env: dict[str, str]) -> list[str]:
        super().get_cargo_command(env)
        return ["cargo", "test"] + self.get_additional_args()
