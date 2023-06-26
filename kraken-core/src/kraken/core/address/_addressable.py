from typing_extensions import Protocol

from ._address import Address


class Addressable(Protocol):
    """
    A protocol that describes objects with an #address attribute. Such objects are considered living in an addressable
    space that can be resolved using an #_address_resolver.AddressSpace and #_address_resolver.resolve_address(). The
    address of any such object is expected to be concrete (see #Address.is_concrete()).
    """

    @property
    def address(self) -> Address:
        raise NotImplementedError
