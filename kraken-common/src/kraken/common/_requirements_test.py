from pathlib import Path

from pytest import raises

from kraken.common import LocalRequirement, PipRequirement, parse_requirement


def test__parse_requirement__can_handle_various_pip_requirements() -> None:
    assert parse_requirement("requests") == PipRequirement("requests", None)
    assert parse_requirement("requests>=0.1.2,<2") == PipRequirement("requests", ">=0.1.2,<2")
    assert parse_requirement("requests >=0.1.2,<2") == PipRequirement("requests", ">=0.1.2,<2")
    assert parse_requirement("abc[xyz,012] !=  2") == PipRequirement("abc", "[xyz,012] !=  2")
    with raises(ValueError):
        assert parse_requirement("!=  2") == PipRequirement("abc", "[xyz,012] !=  2")


def test__parse_requirement__can_handle_local_requirements() -> None:
    assert parse_requirement("kraken-std@.") == LocalRequirement("kraken-std", Path("."))
    assert parse_requirement("abc @ ./abc") == LocalRequirement("abc", Path("./abc"))
    assert parse_requirement("abc@/module/at/abc") == LocalRequirement("abc", Path("/module/at/abc"))
