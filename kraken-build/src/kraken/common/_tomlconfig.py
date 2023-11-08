from collections.abc import Iterator, MutableMapping
from pathlib import Path
from typing import Any, Dict

import tomli
import tomli_w


class TomlConfigFile(MutableMapping[str, Any]):
    """
    A helper class that reads and writes a TOML configuration file.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: "Dict[str, Any] | None" = None

    def _get_data(self) -> "Dict[str, Any]":
        if self._data is None:
            if self.path.is_file():
                self._data = tomli.loads(self.path.read_text())
            else:
                self._data = {}
        return self._data

    def __getitem__(self, key: str) -> Any:
        return self._get_data()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._get_data()[key] = value

    def __delitem__(self, key: str) -> None:
        del self._get_data()[key]

    def __len__(self) -> int:
        return len(self._get_data())

    def __iter__(self) -> Iterator[str]:
        return iter(self._get_data())

    def save(self) -> None:
        self.path.parent.mkdir(exist_ok=True, parents=True)
        self.path.write_text(tomli_w.dumps(self._get_data()))
