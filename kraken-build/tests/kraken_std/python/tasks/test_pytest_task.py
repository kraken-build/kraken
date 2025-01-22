from kraken.core import Project
from kraken.std.python import pytest as pytest_task

FAKE_TEST = """
def test__fake():
    assert True
"""


def test__pytest_single_path(kraken_project: Project) -> None:
    """
    Backwards compatibility test
    """
    (kraken_project.directory / "src").mkdir()
    test_test_dir = kraken_project.directory / "tests"
    test_test_dir.mkdir()
    (test_test_dir / "test_mock.py").write_text(FAKE_TEST)

    task = pytest_task(tests_dir=test_test_dir)

    assert not task.is_skippable()

    kraken_project.context.execute([":test"])


def test__pytest_multiple_paths(kraken_project: Project) -> None:
    src_test_dir = kraken_project.directory / "src"
    test_test_dir = kraken_project.directory / "tests"

    src_test_dir.mkdir()
    test_test_dir.mkdir()

    (src_test_dir / "test_mock.py").write_text(FAKE_TEST)
    (test_test_dir / "test_mock2.py").write_text(FAKE_TEST)

    task = pytest_task(tests_dir=[src_test_dir, test_test_dir])

    assert not task.is_skippable()

    kraken_project.context.execute([":test"])
