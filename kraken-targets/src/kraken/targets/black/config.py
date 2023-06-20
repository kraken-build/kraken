from dataclasses import dataclass

from kraken.targets.core.target import make_target_factory


@dataclass
class BlackConfig:
    """
    Represents a configuration for the Black linter.
    """

    line_length: int | None = None


black_config = make_target_factory("black_config", "black_config", BlackConfig)
