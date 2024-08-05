from pathlib import Path
from typing import cast

from kraken.core import Project
from kraken.std.util.copyright_task import check_and_format_copyright

_TEST_HOLDER = "Test Company"


def test__copyright__execute_contains_check(kraken_project: Project) -> None:
    tasks = check_and_format_copyright(_TEST_HOLDER, project=kraken_project)

    check_execute_list = tasks.check.get_execute_command_v2({})
    assert isinstance(check_execute_list, list)
    assert "-c" in check_execute_list
    assert len(check_execute_list) == 4

    format_execute_list = tasks.format.get_execute_command_v2({})
    assert isinstance(format_execute_list, list)
    assert "-c" not in format_execute_list
    assert len(format_execute_list) == 3


def test__copyright__execute_contains_holder(kraken_project: Project) -> None:
    tasks = check_and_format_copyright(_TEST_HOLDER, project=kraken_project)

    check_execute_list = tasks.check.get_execute_command_v2({})
    assert isinstance(check_execute_list, list)
    assert "-o" in check_execute_list
    assert f"{_TEST_HOLDER}" in check_execute_list
    assert len(check_execute_list) == 4

    format_execute_list = tasks.format.get_execute_command_v2({})
    assert isinstance(format_execute_list, list)
    assert "-o" in format_execute_list
    assert f"{_TEST_HOLDER}" in format_execute_list
    assert len(format_execute_list) == 3


def test__copyright__execute_contains_ignore_when_given(kraken_project: Project) -> None:
    test_str_1 = "build/"
    test_str_2 = "dist/"
    test_ignore = [test_str_1, test_str_2]

    tasks = check_and_format_copyright(_TEST_HOLDER, project=kraken_project, ignore=test_ignore)

    check_execute_list = tasks.check.get_execute_command_v2({})
    assert isinstance(check_execute_list, list)
    assert "-i" in check_execute_list
    assert test_str_1 in check_execute_list
    assert test_str_2 in check_execute_list
    assert len(check_execute_list) == 8

    format_execute_list = tasks.format.get_execute_command_v2({})
    assert isinstance(format_execute_list, list)
    assert "-i" in format_execute_list
    assert test_str_1 in format_execute_list
    assert test_str_2 in format_execute_list
    assert len(format_execute_list) == 7


def test__copyright__execute_contains_license_when_given(kraken_project: Project) -> None:
    license_str = "Test License"

    tasks = check_and_format_copyright(_TEST_HOLDER, project=kraken_project, custom_license=license_str)

    check_execute_list = tasks.check.get_execute_command_v2({})
    assert isinstance(check_execute_list, list)
    assert "-l" in check_execute_list
    assert f"{license_str}" in check_execute_list
    assert len(check_execute_list) == 6

    format_execute_list = tasks.format.get_execute_command_v2({})
    assert isinstance(format_execute_list, list)
    assert "-l" in check_execute_list
    assert f"{license_str}" in format_execute_list
    assert len(format_execute_list) == 5


def test__copyright__execute_contains_license_filepath_when_given(kraken_project: Project, tmpdir: Path) -> None:
    test_license_file = Path(tmpdir) / "test_license.tpl"

    tasks = check_and_format_copyright(_TEST_HOLDER, project=kraken_project, custom_license_file=test_license_file)

    assert str(test_license_file) in cast(list[str], tasks.format.get_execute_command_v2({}))

    check_execute_list = tasks.check.get_execute_command_v2({})
    assert isinstance(check_execute_list, list)
    assert str(test_license_file) in check_execute_list
    assert len(check_execute_list) == 6

    format_execute_list = tasks.format.get_execute_command_v2({})
    assert isinstance(format_execute_list, list)
    assert str(test_license_file) in format_execute_list
    assert len(format_execute_list) == 5
