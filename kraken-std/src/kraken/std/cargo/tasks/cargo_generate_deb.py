import subprocess
from pathlib import Path

from kraken.core import Property, Task, TaskStatus

from kraken.std.descriptors.resource import LibraryArtifact


@dataclass
class CargoDebianArtifact(LibraryArtifact):
    pass


class CargoGenerateDebPackage(Task):
    package_name: Property[str] = Property.default("CargoDebian")
    skip: Property[bool] = Property.default(False)
    message: Property[str | None] = Property.default(None)
    out_packages: Property[list[CargoDebianArtifact]] = Property.output()

    # Task

    def prepare(self) -> TaskStatus:
        if self.skip.get():
            return TaskStatus.skipped(self.message.get())
        return TaskStatus.pending()

    def execute(self) -> TaskStatus:
        package_name = self.package_name.get()
        command = ["cargo", "install", "cargo-deb", "--force"]
        result = subprocess.call(command)
        if result != 0:
            return TaskStatus.from_exit_code(command, result)

        output_deb = f"{package_name}.deb"
        command = ["cargo", "deb", "--output", output_deb]
        result = subprocess.call(command)
        if result != 0:
            return TaskStatus.from_exit_code(command, result)

        out_packages: list[CargoDebianArtifact] = [
            CargoDebianArtifact(package_name, Path(output_deb))
        ]
        self.out_packages.set(out_packages)
        return TaskStatus.succeeded()
