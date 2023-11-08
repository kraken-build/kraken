from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

import tomli
from pytest import fixture

from kraken.common._tomlconfig import TomlConfigFile


@fixture
def tempdir() -> Iterator[Path]:
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test__TomlConfigFile__load_and_save(tempdir: Path) -> None:
    config_file = tempdir / "config.toml"
    config_file.write_text(
        dedent(
            """
        [section]
        key = "value"
        """
        )
    )
    config = TomlConfigFile(config_file)
    assert dict(config) == {"section": {"key": "value"}}
    config["foo"] = "bar"
    config.save()

    assert tomli.loads(config_file.read_text()) == {"section": {"key": "value"}, "foo": "bar"}
