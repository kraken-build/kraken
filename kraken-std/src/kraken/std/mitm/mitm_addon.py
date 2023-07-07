from base64 import b64encode
from json import loads

from mitmproxy import addonmanager, ctx, http


class AuthInjector:
    def __init__(self) -> None:
        self.auth: dict[str, tuple[str, str]] = {}

    def load(self, loader: addonmanager.Loader) -> None:
        loader.add_option(
            name="auth",
            typespec=str,
            help="The auth mapping (host to tuple of (username, password)).",
            default="{}",
        )

    def request(self, flow: http.HTTPFlow) -> None:
        auth = loads(ctx.options.auth)
        if "Authorization" not in flow.request.headers and flow.request.host in auth:
            creds = auth[flow.request.host]
            auth_payload = b64encode(f"{creds[0]}:{creds[1]}".encode()).decode()
            flow.request.headers["Authorization"] = "Basic " + auth_payload


addons = [AuthInjector()]
