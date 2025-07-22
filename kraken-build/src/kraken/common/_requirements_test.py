from pathlib import Path

from pytest import raises

from kraken.common import LocalRequirement, PipRequirement, parse_requirement
from kraken.common._requirements import UrlRequirement


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


def test__parse_requirement__can_handle_url_requirements() -> None:
    assert parse_requirement(
        "kraken-build@ git+https://github.com/kraken-build.git@0.44.2#subdirectory=kraken-build"
    ) == UrlRequirement(
        "kraken-build",
        "git+https://github.com/kraken-build.git@0.44.2#subdirectory=kraken-build",
    )


def test__UrlRequirement__to_uv_source() -> None:
    assert UrlRequirement(
        "kraken-build",
        "git+https://github.com/kraken-build.git@master#subdirectory=kraken-build",
    ).to_uv_source(Path.cwd()) == {
        "git": "https://github.com/kraken-build.git",
        "branch": "master",
        "subdirectory": "kraken-build",
    }

    assert UrlRequirement(
        "kraken-build",
        "git+https://github.com/kraken-build.git@deadbeef#subdirectory=kraken-build",
    ).to_uv_source(Path.cwd()) == {
        "git": "https://github.com/kraken-build.git",
        "rev": "deadbeef",
        "subdirectory": "kraken-build",
    }

    assert UrlRequirement(
        "kraken-build",
        "git+https://github.com/kraken-build.git@deadbeef/imabranch#subdirectory=kraken-build",
    ).to_uv_source(Path.cwd()) == {
        "git": "https://github.com/kraken-build.git",
        "branch": "deadbeef/imabranch",
        "subdirectory": "kraken-build",
    }

    assert UrlRequirement(
        "kraken-build",
        "git+https://github.com/kraken-build.git@0.44.2#subdirectory=kraken-build",
    ).to_uv_source(Path.cwd()) == {
        "git": "https://github.com/kraken-build.git",
        "tag": "0.44.2",
        "subdirectory": "kraken-build",
    }

    assert UrlRequirement(
        "kraken-build",
        "git+https://github.com/kraken-build.git@kraken-build/v0.44.2#subdirectory=kraken-build",
    ).to_uv_source(Path.cwd()) == {
        "git": "https://github.com/kraken-build.git",
        "tag": "kraken-build/v0.44.2",
        "subdirectory": "kraken-build",
    }
