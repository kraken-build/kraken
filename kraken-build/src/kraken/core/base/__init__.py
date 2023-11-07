"""
Provides generic base classes that are relative independent of Kraken itself.
"""

from .currentable import Currentable, CurrentProvider
from .metadata import MetadataContainer

__all__ = [
    "Currentable",
    "CurrentProvider",
    "MetadataContainer",
]
