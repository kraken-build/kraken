from kraken.common._text import pluralize, mask_string


def test__pluralize() -> None:
    assert pluralize("foo", 0) == "foos"
    assert pluralize("foo", 1) == "foo"
    assert pluralize("foo", 2) == "foos"
