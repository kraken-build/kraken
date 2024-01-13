import logging
import shlex
import subprocess
from kraken.build.experimental.common.targets import Executable
from kraken.build.experimental.rules import rule
from kraken.build.experimental.rules.goals import RunGoal

logger = logging.getLogger(__name__)


@rule(persistent_caching=False)
def run_executable(executable: Executable) -> RunGoal:
    logger.info("Running executable $ %s %s", executable.path, " ".join(map(shlex.quote, executable.argv)))
    command = [str(executable.path), *executable.argv]
    exit_code = subprocess.run(command).returncode
    return RunGoal(exit_code=exit_code)
