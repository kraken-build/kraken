from __future__ import annotations

import base64
import json
import logging
import os
from typing import Optional, TypeVar

from proxy.http.parser import HttpParser
from proxy.http.proxy.plugin import HttpProxyBasePlugin

logger = logging.getLogger(__name__)
T = TypeVar("T")


def not_none(v: T | None) -> T:
    assert v is not None
    return v


class AuthInjector(HttpProxyBasePlugin):
    """This proxy.py plugin injects credentials according to the `INJECT_AUTH` environment variable."""

    # TODO (@NiklasRosenstein): Find a better way than environment variables to pass configuration to this plugin.

    _auth: dict[str, tuple[str, str]] | None = None

    @property
    def auth(self) -> dict[str, tuple[str, str]]:
        if self._auth is None:
            self._auth = json.loads(os.environ["INJECT_AUTH"])
        return self._auth

    def handle_client_request(self, request: HttpParser) -> Optional[HttpParser]:
        # NOTE (@NiklasRosenstein): This method is only called for requests in an HTTPS tunnel if TLS
        #       interception is enabled, which requires a self-signed CA-certificate.

        if not request.method or not request.headers:
            return request

        method = request.method.decode()
        host = not_none(request.headers)[b"host"][1].partition(b":")[0].decode()

        if method != "CONNECT" and host in self.auth and not request.has_header(b"Authorization"):
            logger.info("injecting Authorization for %s request to %s", not_none(request.method).decode(), host)
            creds = self.auth[host]
            auth = base64.b64encode(f"{creds[0]}:{creds[1]}".encode())
            request.add_header(b"Authorization", b"Basic " + auth)

        return request
