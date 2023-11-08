from __future__ import annotations

from kraken.core.address import Address, Addressable


class KrakenObject(Addressable):
    """
    A Kraken object is an object that can be addressed in a Kraken context.
    """

    _name: str
    _parent: KrakenObject | None

    def __init__(self, name: str, parent: KrakenObject | None = None):
        assert isinstance(name, str), type(name)
        assert isinstance(parent, KrakenObject) or parent is None, type(parent)
        self._name = name
        self._parent = parent

        # Validate that the name is valid by getting the object's address.
        self.address

    @property
    def name(self) -> str:
        return self._name

    @property
    def address(self) -> Address:
        """
        Returns the full address of the object.
        """

        if self._parent is None:
            return Address.ROOT
        else:
            return self._parent.address.append(self._name)
