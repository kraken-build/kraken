import subprocess
from enum import Enum, auto

from kraken.core import Property, Task, TaskStatus


class CargoHackFeatures(Enum):
    """Feature sets to test"""

    EACH = auto()
    POWERSET = auto()


class CargoHackAction(Enum):
    """CargoHackAction to run for every feature set"""

    CHECK = auto()
    TEST = auto()
    BUILD = auto()


class CargoHackTask(Task):
    description = "Executes cargo hack to verify crate features."
    error_message: Property[str | None] = Property.default(None)
    features: Property[CargoHackFeatures] = Property.default(CargoHackFeatures.EACH)
    action: Property[CargoHackAction] = Property.default(CargoHackAction.CHECK)
    action_arguments: Property[list[str]] = Property.default_factory(list)

    def execute(self) -> TaskStatus:
        command = ["cargo", "hack"]

        match self.features.get():
            case CargoHackFeatures.EACH:
                command.append("--each-feature")
            case CargoHackFeatures.POWERSET:
                command.append("--feature-powerset")
            case _: assert False, f"invalid features={self.features.get()}"

        match self.action.get():
            case CargoHackAction.CHECK:
                command.append("check")
            case CargoHackAction.TEST:
                command.append("test")
            case CargoHackAction.BUILD:
                command.append("build")
            case _: assert False, f"invalid action={self.action.get()}"

        command += self.action_arguments.get()

        result = subprocess.run(command, cwd=self.project.directory)
        if result.returncode == 0:
            return TaskStatus.succeeded()

        return self.error_message.map(
            lambda message: TaskStatus.failed(message)
            if message is not None
            else TaskStatus.from_exit_code(command, result.returncode)
        ).get()
