import hashlib

from kraken.core import Project
from kraken.core.system.task import TaskStatus
from kraken.std.util.validate_readme import ValidateReadmeTask

EXAMPLE_README = """
# project name

This readme is auto generated.
""".lstrip()

BAD_CONTENT_MD5_SUM = hashlib.md5(b"This readme is auto generated.\n").hexdigest()


def _write_example_readme(kraken_project: Project) -> None:
    (kraken_project.directory / "README.md").write_text(EXAMPLE_README)


def test__ValidateReadmeTask__fails_on_no_preferred_readme_file(kraken_project: Project) -> None:
    _write_example_readme(kraken_project)
    task = kraken_project.task("validate_readme", ValidateReadmeTask)
    task.preferred_file_names = ["README.rst"]
    status = task.execute()
    assert status == TaskStatus.failed("completed 1 out of 1 check(s) with errors")
    assert task.statuses.get() == [
        TaskStatus.failed("No preferred readme file found (expected one of: README.rst)"),
    ]


def test__ValidateReadmeTask__warns_on_disallowed_content(kraken_project: Project) -> None:
    _write_example_readme(kraken_project)
    task = kraken_project.task("validate_readme", ValidateReadmeTask)
    task.disallowed_md5_content_hashes = {"bad hash": BAD_CONTENT_MD5_SUM}
    status = task.execute()
    assert status == TaskStatus.warning("completed 1 out of 2 check(s) with warnings")
    assert task.statuses.get() == [
        TaskStatus.succeeded("Found readme file: README.md"),
        TaskStatus.warning("Readme file content matches disallowed hash 'bad hash'"),
    ]


def test__ValidateReadmeTask__warns_on_multiple_readme_files(kraken_project: Project) -> None:
    _write_example_readme(kraken_project)
    (kraken_project.directory / "README.rst").write_text("foobar")
    task = kraken_project.task("validate_readme", ValidateReadmeTask)
    status = task.execute()
    assert status == TaskStatus.warning("completed 1 out of 1 check(s) with warnings")
    assert task.statuses.get() == [
        TaskStatus.warning("Found multiple readme files. Linting only README.md"),
    ]


def test__ValidateReadmeTask__warns_about_disallowed_pattern_match(kraken_project: Project) -> None:
    _write_example_readme(kraken_project)
    task = kraken_project.task("validate_readme", ValidateReadmeTask)
    task.disallowed_regex_patterns = [r"auto\s*generated"]
    status = task.execute()
    assert status == TaskStatus.warning("completed 1 out of 2 check(s) with warnings")
    assert task.statuses.get() == [
        TaskStatus.succeeded("Found readme file: README.md"),
        TaskStatus.warning(r"Readme file contains disallowed pattern auto\s*generated"),
    ]


def test__ValidateReadmeTask__warns_about_minimum_lines(kraken_project: Project) -> None:
    _write_example_readme(kraken_project)
    task = kraken_project.task("validate_readme", ValidateReadmeTask)
    task.minimum_lines = 10
    status = task.execute()
    assert status == TaskStatus.warning("completed 1 out of 2 check(s) with warnings")
    assert task.statuses.get() == [
        TaskStatus.succeeded("Found readme file: README.md"),
        TaskStatus.warning(r"Readme file has less than 10 lines (got: 4)"),
    ]
