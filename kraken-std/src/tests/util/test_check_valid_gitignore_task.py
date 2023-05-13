from pathlib import Path

from kraken.core.testing import kraken_ctx, kraken_project

from kraken.std.git import GitignoreCheckTask

DATA_DIR = Path(__file__).parent / "data" / "gitignore"
NO_GITIGNORE_DIR = DATA_DIR
EMPTY_GITIGNORE_DIR = DATA_DIR / "gitignore_empty"
CORRUPT_CONTENT_GITIGNORE_DIR = DATA_DIR / "gitignore_corrupt_content"
CORRUPT_HASH_GITIGNORE_DIR = DATA_DIR / "gitignore_corrupt_hash"
UNSORTED_GITIGNORE_DIR = DATA_DIR / "gitignore_unsorted"
VALID_GITIGNORE_DIR = DATA_DIR / "gitignore_valid"


def test__gitignore_does_not_exist() -> None:
    with kraken_ctx() as ctx, kraken_project(ctx) as project:
        project.directory = NO_GITIGNORE_DIR
        test_task = project.do("test__gitignore_does_not_exist", GitignoreCheckTask, group="check", tokens=[])
        assert test_task.execute().is_failed()


def test__gitignore_is_not_empty() -> None:
    with kraken_ctx() as ctx, kraken_project(ctx) as project:
        project.directory = EMPTY_GITIGNORE_DIR
        test_task = project.do("test__gitignore_is_not_empty", GitignoreCheckTask, group="check", tokens=[])
        assert test_task.execute().is_failed()


def test__gitignore_has_unmodified_hash() -> None:
    with kraken_ctx() as ctx, kraken_project(ctx) as project:
        project.directory = CORRUPT_HASH_GITIGNORE_DIR
        test_task = project.do("test__gitignore_has_unmodified_hash", GitignoreCheckTask, group="check", tokens=[])
        assert test_task.execute().is_failed()


def test__gitignore_has_unmodified_content() -> None:
    with kraken_ctx() as ctx, kraken_project(ctx) as project:
        project.directory = CORRUPT_CONTENT_GITIGNORE_DIR
        test_task = project.do("test__gitignore_has_unmodified_content", GitignoreCheckTask, group="check", tokens=[])
        assert test_task.execute().is_failed()


def test__gitignore_has_correct_tokens() -> None:
    with kraken_ctx() as ctx, kraken_project(ctx) as project:
        project.directory = VALID_GITIGNORE_DIR
        test_task = project.do("test__gitignore_has_correct_tokens", GitignoreCheckTask, group="check", tokens=["test"])
        assert test_task.execute().is_failed()


def test__gitignore_is_sorted() -> None:
    with kraken_ctx() as ctx, kraken_project(ctx) as project:
        project.directory = UNSORTED_GITIGNORE_DIR
        test_task = project.do("test__gitignore_is_sorted", GitignoreCheckTask, group="check", tokens=[])
        assert test_task.execute().is_failed()


def test__gitignore_passes_when_valid() -> None:
    with kraken_ctx() as ctx, kraken_project(ctx) as project:
        project.directory = VALID_GITIGNORE_DIR
        test_task = project.do("test__gitignore_passed_when_valid", GitignoreCheckTask, group="check", tokens=[])
        assert test_task.execute().is_up_to_date()
