import os
import tempfile
from pathlib import Path

import pytest
from kraken.common import findpython

from kraken.targets.python.venv import CreateVenvRequest, CreateVenvResponse
from kraken.targets.rulerunner import RuleRunner


@pytest.fixture
def runner() -> RuleRunner:
    return RuleRunner(["kraken.targets.python.binary", "kraken.targets.python.venv"])


def test__create_venv(runner: RuleRunner) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        request = CreateVenvRequest(path=Path(tmpdir) / "venv", interpreter_constraint=">=3.10")
        response = runner.get(CreateVenvResponse, [request])

        python_bin = response.scripts_dir / ("python.exe" if os.name == "nt" else "python")
        assert response.python.path == python_bin
        assert findpython.get_python_interpreter_version(response.python.path) == response.python.version
