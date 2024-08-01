"""
Helper functions to access test resources.
"""

from pathlib import Path


def repository_root() -> Path:
    """Returns the path to the root of the repository."""
    path = Path(__file__).parent.parent
    assert path.name == "kraken-build"
    return path.parent


def example_dir(name: str) -> Path:
    """Returns the path to the example directory."""
    return repository_root() / "examples" / name
