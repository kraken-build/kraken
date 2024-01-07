from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class InstallGoal:
    """Represents the goal of installing a target."""

    pass


@dataclass(frozen=True, kw_only=True)
class BuildGoal:
    """Represents the goal of building a target."""

    pass


@dataclass(frozen=True, kw_only=True)
class RunGoal:
    """Represents the goal of running a target."""

    exit_code: int
