from __future__ import annotations

from subprocess import run
from sys import stderr

from kraken.core import Property, Task

from ..config import CargoRegistry


class CargoLoginTask(Task):
    """This task runs cargo login for each registry."""

    #: The registries to insert into the configuration.
    registries: Property[list[CargoRegistry]] = Property.default_factory(list)

    def execute(self) -> None:
        for registry in self.registries.get():
            publish_token = registry.publish_token
            if publish_token is None:
                continue
            p = run(
                ["cargo", "login", "--registry", registry.alias],
                cwd=self.project.directory,
                capture_output=True,
                input=publish_token.encode(),
            )
            if p.returncode != 0:
                if p.stderr.endswith(b"\nerror: config.json not found in registry\n"):
                    # This happens when the project's .cargo/config.toml file
                    # contains a regitry which does not exist (anymore); since
                    # that means it is not used, we can just skip configuring
                    # authentication on this registry
                    pass
                else:
                    # unknown error, fail normally
                    print(repr(p.stderr))
                    stderr.write(p.stderr.decode())
                    p.check_returncode()
