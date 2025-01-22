import pytest

from kraken.std.git.gitignore.gitignore_io import TOKENS, gitignore_io_fetch_cached, load_token_cache


def test__gitignore_io_cache_for_every_token() -> None:
    assert set(load_token_cache()) == set(TOKENS)


def test__gitignore_io_fetch_cached__errors_without_backfil_on_missing_token() -> None:
    with pytest.raises(ValueError) as excinfo:
        gitignore_io_fetch_cached(["missing-token"], backfill=False)
    assert str(excinfo.value) == (
        "The following gitignore.io tokens are not distributed as part of kraken-std: missing-token\n"
        "Backfill is disabled, so this error is raised instead of making another HTTP request to gitignore.io."
    )
