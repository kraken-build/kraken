"""
This module provides the :class:`Address` class and related classes and methods to work with addresses and
addressable objects.
"""

from ._address import Address
from ._address_resolver import AddressResolutionError, AddressResolutionResult, AddressSpace, resolve_address
from ._addressable import Addressable

__all__ = [
    "Address",
    "AddressResolutionResult",
    "Addressable",
    "AddressSpace",
    "AddressResolutionError",
    "resolve_address",
]
