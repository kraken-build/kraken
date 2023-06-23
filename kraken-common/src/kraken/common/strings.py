from __future__ import annotations


def as_bytes(v: str | bytes, encoding: str) -> bytes:
    return v.encode(encoding) if isinstance(v, str) else v
