from kraken.std.util.url import inject_url_credentials


def test_inject_url_credentials() -> None:
    assert (
        inject_url_credentials("http://localhost:8000/simple/", "foo", "bar") == "http://foo:bar@localhost:8000/simple/"
    )
