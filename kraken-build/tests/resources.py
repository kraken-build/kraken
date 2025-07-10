"""
Helper functions to access test resources.
"""

from pathlib import Path


def data_path(name: str) -> Path:
    """Returns the path to a file or directory in the tests data directory."""

    return (Path(__file__).parent / "data" / name).resolve()
