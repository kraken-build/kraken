from kraken.common._text import pluralize, mask_string


def test__pluralize() -> None:
    assert pluralize("foo", 0) == "foos"
    assert pluralize("foo", 1) == "foo"
    assert pluralize("foo", 2) == "foos"


def test__mask_string() -> None:
    # Group: Input string too short relative to unmasked total
    assert mask_string("passwor", 1) == "[MASKED]"
    assert mask_string("password", 1) == "[MASKED]"
    assert mask_string("password__", 2) == "[MASKED]"
    assert mask_string("password_", 1) == "[MASKED]"

    # Group: Mask OK
    assert mask_string("pass__word", 1) == "p[MASKED]d"
    assert mask_string("password__", 1) == "p[MASKED]_"

    # Group: Edge cases
    assert mask_string("", 0) == "[MASKED]"
    assert mask_string("", 1) == "[MASKED]"
    assert mask_string("", -1) == "[MASKED]"
    assert mask_string("password", -1) == "[MASKED]"  # Non-sensible start/end plain count
