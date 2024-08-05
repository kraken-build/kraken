import logging
import time
from collections.abc import Collection

import httpx

from kraken.common import http

logger = logging.getLogger(__name__)


def http_probe(method: str, url: str, timeout: float = 60, status_codes: Collection[int] | None = None) -> None:
    """Probe an HTTP URL for an expected status code, for max *timeout* seconds."""

    logger.info("Probing %s %s (timeout: %d)", method, url, timeout)

    status_codes = range(200, 4000) if status_codes is None else status_codes
    tstart = time.perf_counter()
    idx = 0
    while (time.perf_counter() - tstart) < timeout or idx == 0:  # At least one iteration
        idx += 1
        try:
            request = http.request(method, url)
        except httpx.RequestError as exc:
            logger.debug("Ignoring error while probing (%s)", exc)
        else:
            if request.status_code in status_codes:
                logger.info("Probe returned status code %d (expected)", request.status_code)
                return
            logger.debug("Probe returned status code %d (continue probing)", request.status_code)
        time.sleep(0.5)

    raise TimeoutError("Probe timed out")
