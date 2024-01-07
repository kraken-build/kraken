import logging
import subprocess
from kraken.build.common.targets import Executable
from kraken.build.rules import rule
from kraken.build.rules.goals import RunGoal

logger = logging.getLogger(__name__)


@rule()
def run_executable(executable: Executable) -> RunGoal:
    logger.debug("Running executable: %s %s", executable.path, executable.argv)
    command = [str(executable.path), *executable.argv]
    exit_code = subprocess.run(command).returncode
    return RunGoal(exit_code=exit_code)
