"""Bin module."""

import httpx


def main() -> str:  # intentionally missing return
    """Bin function"""
    _response: httpx.Response = httpx.get("https://example.com")
