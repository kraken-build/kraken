from kraken.common.sanitize import sanitize_http_basic_auth


def test_sanitize_http_basic_auth() -> None:
    assert (
        sanitize_http_basic_auth("$ pip install --extra-index-url https://foo:bar@pypi.org/simple")
        == "$ pip install --extra-index-url https://foo:[MASKED]@pypi.org/simple"
    )
