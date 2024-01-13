from dataclasses import dataclass
from pathlib import Path
from kraken.core import Target


@dataclass(frozen=True, kw_only=True)
class Executable(Target):
    """Represents an executable that can be run."""

    path: Path
    argv: tuple[str, ...] = ()
