from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit


@dataclass
class TomlFile(MutableMapping[str, Any]):
    """
    Represents a raw `.toml` file in deserialized form, with some convenience functions to read/write it from/to a file,
    using `tomlkit` to maintain formatting as much as possible when writing back.
    """

    path: Path | None
    data: MutableMapping[str, Any]

    def __init__(self, path: Path | None, data: MutableMapping[str, Any]) -> None:
        self.path = path
        self.data = data

    def __iter__(self) -> Iterator[str]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value

    def __delitem__(self, key: str) -> None:
        del self.data[key]

    def setdefault(self, key: str, default: Any | None = None) -> Any:
        # NOTE(@niklas): We need to override this as the default implementation from MutableMapping is not
        #       compatible with the expected behaviour from the wrapped Tomlkit container. See
        #       https://github.com/sdispater/tomlkit/issues/49#issuecomment-1999713939
        self.data.setdefault(key, default)
        return self.data[key]

    @classmethod
    def read_string(cls, text: str) -> "TomlFile":
        return cls(None, tomlkit.parse(text))

    @classmethod
    def read(cls, path: Path) -> "TomlFile":
        with path.open("rb") as fp:
            return cls(path, tomlkit.load(fp))

    def save(self, path: Path | None = None) -> None:
        path = path or self.path
        if not path:
            raise RuntimeError("No path to save to")
        with path.open("w") as fp:
            fp.write(self.to_toml_string())

    def to_toml_string(self) -> str:
        return tomlkit.dumps(self.data)
