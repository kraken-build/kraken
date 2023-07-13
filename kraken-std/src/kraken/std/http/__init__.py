# Perform HTTP requests
# This module internally calls httpx, but with a custom setup

import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx

__all__ = ["request", "get", "options", "head", "post", "put", "patch", "delete", "stream"]

_CACHED_SYSTEM_CA_LIST: ssl.SSLContext | None = None


# Caching calls to ssl.create_default_context()
# Using functools.cache does not play well with mypy (https://github.com/python/mypy/issues/5107),
# so I'm implementing my own cache
def _get_system_ca_list() -> ssl.SSLContext:
    """
    Corporate proxies may replace the original SSL cert by their own.
    In this case, their cert should be part of the system list of accepted root CAs, and this is the one we
    should use, instead of httpx' default (which otherwise uses the list provided by certifi)
    """
    global _CACHED_SYSTEM_CA_LIST
    if _CACHED_SYSTEM_CA_LIST is None:
        _CACHED_SYSTEM_CA_LIST = ssl.create_default_context()
    return _CACHED_SYSTEM_CA_LIST


def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    return httpx.request(method, url, verify=_get_system_ca_list(), **kwargs)


def get(url: str, **kwargs: Any) -> httpx.Response:
    return httpx.get(url, verify=_get_system_ca_list(), **kwargs)


def options(url: str, **kwargs: Any) -> httpx.Response:
    return httpx.options(url, verify=_get_system_ca_list(), **kwargs)


def head(url: str, **kwargs: Any) -> httpx.Response:
    return httpx.head(url, verify=_get_system_ca_list(), **kwargs)


def post(url: str, **kwargs: Any) -> httpx.Response:
    return httpx.post(url, verify=_get_system_ca_list(), **kwargs)


def put(url: str, **kwargs: Any) -> httpx.Response:
    return httpx.put(url, verify=_get_system_ca_list(), **kwargs)


def patch(url: str, **kwargs: Any) -> httpx.Response:
    return httpx.patch(url, verify=_get_system_ca_list(), **kwargs)


def delete(url: str, **kwargs: Any) -> httpx.Response:
    return httpx.delete(url, verify=_get_system_ca_list(), **kwargs)


# Forwarding calls to `stream` would not be accepted as-is by mypy.
# Let's trick a bit
@contextmanager
def stream(url: str, **kwargs: Any) -> Iterator[httpx.Response]:
    with httpx.stream(url, verify=_get_system_ca_list(), **kwargs) as stream:
        yield stream
