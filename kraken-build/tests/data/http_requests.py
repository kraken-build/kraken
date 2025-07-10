# This file has examples of constructs that should be disallowed by some of our custom linters

import httpx
import requests  # type: ignore[import-untyped]

from kraken.common import http


def please_dont_do_this_dear() -> None:
    """
    Call a method of httpx. This is disallowed, as http.get() should be used instead
    """
    reply = httpx.get("http://www.xkcd.com")
    reply.raise_for_status()


def i_told_you_not_to_do_this() -> None:
    """
    Call a method of requests. This is disallowed, as http.get() should be used instead
    """
    reply1 = requests.get("http://www.xkcd.com")
    reply1.raise_for_status()
    reply2 = requests.post("http://www.xkcd.com")
    reply2.raise_for_status()


def now_thats_a_good_boy() -> None:
    """
    This calls a method using the `http` wrapper module, this is allowed.
    This uses a constant defined in requests, but that is allowed as well (constants are
    not re-exported by our `http` module)
    """
    reply = http.get("http://www.xkcd.com")
    assert reply.status_code != requests.codes.teapot
