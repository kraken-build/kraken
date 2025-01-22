import pytest

from kraken.core import BuildError, Project
from kraken.std.python import ruff

BAD_SCRIPT = 'a="a"'

GOOD_SCRIPT = 'a = "a"\n'


@pytest.mark.parametrize("script", (GOOD_SCRIPT, BAD_SCRIPT))
def test__ruff__apply_fmt_success(kraken_project: Project, script: str) -> None:
    (kraken_project.directory / "src").mkdir()
    kraken_project.directory.joinpath("src/pyfile.py").write_text(script)
    ruff()
    kraken_project.context.execute([":fmt"])

    # Check that the formatted file corresponds to the expected one
    assert kraken_project.directory.joinpath("src/pyfile.py").read_text() == GOOD_SCRIPT


def test__ruff__lint_success(kraken_project: Project) -> None:
    (kraken_project.directory / "src").mkdir()
    kraken_project.directory.joinpath("src/pyfile.py").write_text(GOOD_SCRIPT)
    ruff()
    # Expect linting to run without error on GOOD_SCRIPT
    kraken_project.context.execute([":lint"])


def test__ruff__lint_fail(kraken_project: Project) -> None:
    (kraken_project.directory / "src").mkdir()
    kraken_project.directory.joinpath("src/pyfile.py").write_text(BAD_SCRIPT)
    ruff()
    # Expect linting to fail on BAD_SCRIPT
    with pytest.raises(BuildError, match=r'task ":python\.ruff\.(?:fmt\.check|fmt)" failed'):
        kraken_project.context.execute([":lint"])


@pytest.mark.parametrize("script", (GOOD_SCRIPT, BAD_SCRIPT))
def test__ruff__fmt_lint_success(kraken_project: Project, script: str) -> None:
    (kraken_project.directory / "src").mkdir()
    kraken_project.directory.joinpath("src/pyfile.py").write_text(script)
    ruff()
    kraken_project.context.execute([":fmt", ":lint"])

    # Check that the formatted file corresponds to the expected one
    assert kraken_project.directory.joinpath("src/pyfile.py").read_text() == GOOD_SCRIPT
