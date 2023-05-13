from pathlib import Path

from kraken.std.util.check_valid_readme_exists_task import CheckValidReadmeExistsError, CheckValidReadmeExistsTask

DATA_DIR = Path(__file__).parent / "data"
NO_README_DIR = DATA_DIR
EMPTY_README_DIR = DATA_DIR / "readme_empty"
INVALID_README_DIR = DATA_DIR / "readme_invalid"
TEST_README_CONTENT_NOT_ALLOWED = ["68cdf6207484da6229eeddde80345d96a2127f18a2428ac3167c42cfc61dd86c"]


def test__readme_does_not_exist() -> None:
    result = CheckValidReadmeExistsTask._check(NO_README_DIR, [])
    assert result[CheckValidReadmeExistsError.DOES_NOT_EXIST]


def test__readme_file_name_is_invalid() -> None:
    result = CheckValidReadmeExistsTask._check(INVALID_README_DIR, [])
    assert result[CheckValidReadmeExistsError.INVALID_FILENAME]


def test__empty_readme_does_not_throw_exceptions() -> None:
    result = CheckValidReadmeExistsTask._check(EMPTY_README_DIR, [])
    assert result[CheckValidReadmeExistsError.FILE_TOO_SHORT]


def test__readme_does_not_have_enough_content() -> None:
    result = CheckValidReadmeExistsTask._check(INVALID_README_DIR, [])
    assert result[CheckValidReadmeExistsError.FILE_TOO_SHORT]


def test__readme_content_is_not_allowed() -> None:
    result = CheckValidReadmeExistsTask._check(INVALID_README_DIR, TEST_README_CONTENT_NOT_ALLOWED)
    assert result[CheckValidReadmeExistsError.CONTENT_NOT_ALLOWED]
