from __future__ import annotations

import configparser
import io
from pathlib import Path
from typing import TextIO


def load_gitconfig(file: TextIO | Path | str) -> dict[str, dict[str, str]]:
    """Parses a Git configuration file."""

    if isinstance(file, str):
        return load_gitconfig(io.StringIO(file))
    elif isinstance(file, Path):
        with file.open() as fp:
            return load_gitconfig(fp)

    parser = configparser.RawConfigParser()
    parser.read_file(file)
    result = dict(parser._sections)  # type: ignore[attr-defined]
    for k in result:
        result[k] = dict(parser._defaults, **result[k])  # type: ignore[attr-defined]
        result[k].pop("__name__", None)
    return result


def dump_gitconfig(data: dict[str, dict[str, str]]) -> str:
    """Formats a Git configuration file."""

    parser = configparser.RawConfigParser()
    for section, values in data.items():
        parser.add_section(section)
        for key, value in values.items():
            parser.set(section, key, value)
    fp = io.StringIO()
    parser.write(fp)
    return fp.getvalue()
