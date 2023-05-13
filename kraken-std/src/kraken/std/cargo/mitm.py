"""
Implements a MITM proxy server using the :mod:`proxy` (`proxy.py` on PyPI) module to inject the auth credentials
into Cargo and Git HTTP(S) requests.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import subprocess as sp
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def mitm_auth_proxy(
    auth: dict[str, tuple[str, str]],
    port: int = 8899,
    timeout: float | None = None,
) -> Iterator[tuple[str, Path]]:
    """Runs a MITM HTTPS proxy that injects credentials according to *auth* into requests."""

    if timeout is None and "PROXY_PY_TIMEOUT" in os.environ:
        timeout = int(os.environ["PROXY_PY_TIMEOUT"])

    certs_dir = Path(__file__).parent / "data" / "certs"
    key_file = certs_dir / "key.pem"
    cert_file = certs_dir / "cert.pem"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent) + os.pathsep + env.get("PYTHONPATH", "")

    # Find the proxy command.
    proxy_cmd = shutil.which("proxy")
    if not proxy_cmd:
        raise FileNotFoundError(
            "The `proxy` command could not be found. Usually it is automatically available when using kraken-wrapper. "
            "If you are running on a kraken-wrapper version before 0.2.2, please upgrade. As an alternative, but less "
            "recommended workaround, you can run `pipx install proxy.py` followed by `pipx inject proxy.py certifi`."
        )

    command = [
        proxy_cmd,
        "--plugins",
        "mitm_impl.AuthInjector",
        "--ca-key-file",
        str(key_file),
        "--ca-cert-file",
        str(cert_file),
        "--ca-signing-key",
        str(key_file),
        "--port",
        str(port),
    ]

    if timeout is not None:
        command += ["--timeout", str(timeout)]

    env["INJECT_AUTH"] = json.dumps(auth)
    env["PYTHONWARNINGS"] = "ignore"

    logger.info("starting proxy server: %s", command)
    proc = sp.Popen(command, env=env)

    try:
        yield f"http://localhost:{port}", cert_file
    finally:
        logger.info("stopping proxy server")
        proc.terminate()
        proc.wait()
        if proc.returncode is None:
            proc.kill()
            proc.wait()
