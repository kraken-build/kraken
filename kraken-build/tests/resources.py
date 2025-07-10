"""
Helper functions to access test resources.
"""

from pathlib import Path


def data_path(name: str) -> Path:
    """Returns the path to the example directory."""

    return Path(__file__).parent / "data" / name
