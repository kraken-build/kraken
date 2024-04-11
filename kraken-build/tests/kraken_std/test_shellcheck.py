import pytest

from kraken.core import BuildError, Project
from kraken.std.shellcheck import shellcheck

BAD_SCRIPT = """#!/bin/bash
if [ -z "$foo"] ; then
    echo "bar"
fi
"""

GOOD_SCRIPT = """#!/bin/bash
if [ -z "$foo" ]; then
    echo "bar"
fi
"""


def test__shellcheck__bad_script(kraken_project: Project) -> None:
    kraken_project.directory.joinpath("script.sh").write_text(BAD_SCRIPT)
    shellcheck(files=["script.sh"])
    with pytest.raises(BuildError) as excinfo:
        kraken_project.context.execute([":lint"])
    assert {str(x.address) for x in excinfo.value.failed_tasks} == {":shellcheck"}


def test__shellcheck__good_script(kraken_project: Project) -> None:
    kraken_project.directory.joinpath("script.sh").write_text(GOOD_SCRIPT)
    shellcheck(files=["script.sh"])
    kraken_project.context.execute([":lint"])
