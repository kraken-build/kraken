"""
Manages a `mitmweb` instance to run in the background for injecting basic-auth into requests to hosts for which
credentials are passed down. The `mitmweb` web interface can be reached on `localhost:8900` while it is running.
The proxy stays alive as a daemon process until its configuration changes.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

from kraken.std.util.daemon_controller import DaemonController
from kraken.std.util.http import http_probe

logger = logging.getLogger(__name__)

daemon_state_file = Path("~/.config/krakenw/.mitmweb-daemon-state.json").expanduser()
daemon_log_file = daemon_state_file.with_suffix(".log")
mitmweb_port = 8899
mitmweb_ui_port = 8900
mitmproxy_ca_cert_file = Path("~/.mitmproxy/mitmproxy-ca-cert.pem").expanduser()
inject_auth_addon_file = Path(__file__).parent / "mitm_addon.py"


def start_mitmweb_proxy(
    auth: Mapping[str, tuple[str, str]],
    mitmweb_cmd: Sequence[str] = ("mitmweb",),
    additional_args: Sequence[str] = (),
) -> tuple[str, Path]:
    """
    Ensure that a `mitmweb` process with the given *auth* configuration and *additional_args* is running. If a
    process is already running that doesn't match the spec, it will be stopped and a new one will be started.

    Note:
        This process is managed globally and the state is stored under `~/.mitmproxy`. Switching between projects
        that require a different configuration will stop and start the proxy constantly.
    """

    controller = DaemonController("kraken.mitmweb", daemon_state_file)
    started = controller.run(
        command=[
            *mitmweb_cmd,
            "--no-web-open-browser",
            "--web-port",
            str(mitmweb_ui_port),
            "--listen-port",
            str(mitmweb_port),
            "-s",
            str(inject_auth_addon_file),
            "--set",
            "auth=" + json.dumps(auth),
            # `mitmproxy` buffers the entire response before forwarding it to
            # the client. This is problematic when e.g. cloning large git repos
            # via http. As we're not using any filtering mechanism, we can just
            # stream the bodies through without `mitmproxy` storing them.
            #
            # See https://github.com/mitmproxy/mitmproxy/issues/6237 for
            # context.
            "--set",
            "stream_large_bodies=3m",
            *additional_args,
        ],
        cwd=Path("~").expanduser(),
        stdout=daemon_log_file,
        stderr="stdout",
    )

    # Wait for the proxy to come up. It will respond with a 502 code because there's no
    # additioal information in the request to tell it what to proxy.
    try:
        http_probe("GET", f"http://localhost:{mitmweb_port}", status_codes={502}, timeout=60 if started else 0)
    except TimeoutError:
        logger.error("mitmweb did not start in time, check the log file at %s", daemon_log_file)
        controller.stop()
        raise

    if started:
        print("mitmweb was started successfully")
    else:
        print("mitmweb already running")

    print(f"proxy available at http://localhost:{mitmweb_port}")
    print(f"web ui available at http://localhost:{mitmweb_ui_port}")
    return f"localhost:{mitmweb_port}", mitmproxy_ca_cert_file


def stop_mitmweb_proxy() -> None:
    controller = DaemonController("kraken.mitmweb", daemon_state_file)
    controller.stop()
