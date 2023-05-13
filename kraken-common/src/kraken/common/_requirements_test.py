from io import StringIO
from pathlib import Path

from pytest import raises

from kraken.common import (
    LocalRequirement,
    PipRequirement,
    RequirementSpec,
    deprecated_get_requirement_spec_from_file_header,
    parse_requirement,
)


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


def test__deprecated_get_requirement_spec_from_file_header() -> None:
    fp = StringIO("# ::requirements kraken-std>=0.5.10 --index-url https://testpypi.org/simple\n" "# ::pythonpath foo")
    assert deprecated_get_requirement_spec_from_file_header(fp) == RequirementSpec(
        requirements=(parse_requirement("kraken-std>=0.5.10"),),
        index_url="https://testpypi.org/simple",
        pythonpath=("foo", "build-support"),
    )
