from typing import Dict, List

from .cargo_build_task import CargoBuildTask


class CargoTestTask(CargoBuildTask):
    """This task runs `cargo test` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    description = "Run `cargo test`."

    def get_cargo_command(self, env: Dict[str, str]) -> List[str]:
        super().get_cargo_command(env)
        return ["cargo", "test"] + self.additional_args.get()
