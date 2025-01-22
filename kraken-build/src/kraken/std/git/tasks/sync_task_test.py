import textwrap

from pytest import raises

from kraken.core import BuildError, Project
from kraken.std.git import gitignore
from kraken.std.git.tasks.sync_task import GitignoreSyncTask

NO_GENERATED_CONTENT = """
# This is a comment
and/a/path
"""

WITH_GENERATED_CONTENT = """
foo
# GENERATED-CONTENT-START
bar
# GENERATED-CONTENT-END
baz
"""


def test__GitignoreSyncTask__inserts_generated_content_on_top(kraken_project: Project) -> None:
    path = kraken_project.directory / ".gitignore"
    path.write_text(NO_GENERATED_CONTENT)
    task = kraken_project.task("gitignore", GitignoreSyncTask)
    task.finalize()
    print(task.prepare())
    print(task.execute())
    assert (
        path.read_text()
        == textwrap.dedent(
            """
        # GENERATED-CONTENT-START
        # Kraken
        /build
        # GENERATED-CONTENT-END

        # This is a comment
        and/a/path
        """
        ).lstrip()
    )


def test__GitignoreSyncTask__inserts_generated_content_on_bottom(kraken_project: Project) -> None:
    path = kraken_project.directory / ".gitignore"
    path.write_text(NO_GENERATED_CONTENT)
    task = kraken_project.task("gitignore", GitignoreSyncTask)
    task.where = "bottom"
    task.finalize()
    print(task.prepare())
    print(task.execute())
    assert path.read_text() == textwrap.dedent(
        """
        # This is a comment
        and/a/path

        # GENERATED-CONTENT-START
        # Kraken
        /build
        # GENERATED-CONTENT-END
        """
    )


def test__GitignoreSyncTask__updates_existing_generated_content(kraken_project: Project) -> None:
    path = kraken_project.directory / ".gitignore"
    path.write_text(WITH_GENERATED_CONTENT)
    task = kraken_project.task("gitignore", GitignoreSyncTask)
    task.finalize()
    print(task.prepare())
    print(task.execute())
    assert path.read_text() == textwrap.dedent(
        """
        foo

        # GENERATED-CONTENT-START
        # Kraken
        /build
        # GENERATED-CONTENT-END

        baz
        """
    )


def test__gitignore__check_and_apply_tasks(kraken_project: Project) -> None:
    gitignore(gitignore_io_tokens=["python"])[0]
    with raises(BuildError):
        kraken_project.context.execute([":check"])
    kraken_project.context.execute([":apply"])
    kraken_project.context.execute([":check"])
