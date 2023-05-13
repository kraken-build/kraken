from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import Iterator, List
from urllib.parse import urlparse

import tomli
import tomli_w
from kraken.common import atomic_file_swap, not_none
from kraken.core.api import BackgroundTask, Property, TaskStatus

from kraken.std.cargo.config import CargoRegistry
from kraken.std.git.config import dump_gitconfig, load_gitconfig

logger = logging.getLogger(__name__)


class CargoAuthProxyTask(BackgroundTask):
    """This task starts a local proxy server that injects HTTP basic authentication credentials in HTTP(S) requests
    to a Cargo repository to work around Cargo's current inability to interface with private repositories."""

    description = "Creates a proxy that injects credentials to route Cargo traffic through."

    #: The Cargo config file to update.
    cargo_config_file: Property[Path] = Property.default(".cargo/config.toml")

    #: A list of the Cargo registries for which to inject credentials for based on matching paths.
    registries: Property[List[CargoRegistry]]

    #: The proxy port.
    proxy_port: Property[int] = Property.default(8899)

    #: The URL of the proxy. This property is only valid and accessible for tasks that immediately directly depend
    #: on this task and will be invalidated at the task teardown.
    proxy_url: Property[str] = Property.output()

    #: The path to the certificate file that needs to be trusted in order to talk to the proxy over HTTPS.
    proxy_cert_file: Property[Path] = Property.output()

    #: The number of seconds to wait after the proxy started.
    startup_wait_time: Property[float] = Property.default(1.0)

    #: The number of seconds the proxy must be alive at least before terminating it. This is to avoid cryptic error
    #: messages if the proxy is killed during it's startup time.
    min_lifetime: Property[float] = Property.default(2.0)

    @contextlib.contextmanager
    def _inject_config(self) -> Iterator[None]:
        """Injects the proxy URL and cert file into the Cargo and Git configuration."""

        # TODO (@NiklasRosenstein): Can we get away without temporarily modifying the GLOBAL Git config?

        cargo_config_toml = self.project.directory / self.cargo_config_file.get()
        cargo_config = tomli.loads(cargo_config_toml.read_text()) if cargo_config_toml.is_file() else {}

        git_config_file = Path("~/.gitconfig").expanduser()
        git_config = load_gitconfig(git_config_file) if git_config_file.is_file() else {}

        with contextlib.ExitStack() as exit_stack:
            # Temporarily update the Cargo configuration file to inject the HTTP(S) proxy and CA info.
            cargo_http = cargo_config.setdefault("http", {})
            cargo_http["proxy"] = self.proxy_url.get()
            cargo_http["cainfo"] = str(self.proxy_cert_file.get().absolute())

            for registry in self.registries.get():
                if not registry.read_credentials:
                    continue
                if registry.alias in cargo_config["registries"]:
                    entry = cargo_config["registries"][registry.alias]
                    entry["token"] = f"Bearer {registry.read_credentials[1]}"

            logger.info("updating %s", cargo_config_toml)
            fp = exit_stack.enter_context(
                atomic_file_swap(cargo_config_toml, "w", always_revert=True, create_dirs=True)
            )
            fp.write(tomli_w.dumps(cargo_config))
            fp.close()

            # Temporarily update the Git configuration file to inject the HTTP(S) proxy and CA info.
            git_http = git_config.setdefault("http", {})
            git_http["proxy"] = self.proxy_url.get()
            git_http["sslCAInfo"] = str(self.proxy_cert_file.get().absolute())
            logger.info("updating %s", git_config_file)
            fp = exit_stack.enter_context(atomic_file_swap(git_config_file, "w", always_revert=True, create_dirs=True))
            fp.write(dump_gitconfig(git_config))
            fp.close()

            yield

    # Task

    def start_background_task(self, exit_stack: contextlib.ExitStack) -> TaskStatus:
        from ..mitm import mitm_auth_proxy

        auth: dict[str, tuple[str, str]] = {}
        for registry in self.registries.get():
            if not registry.read_credentials:
                continue
            host = not_none(urlparse(registry.index).hostname)
            auth[host] = registry.read_credentials

        try:
            proxy_url, cert_file = exit_stack.enter_context(mitm_auth_proxy(auth=auth, port=self.proxy_port.get()))
        except FileNotFoundError as exc:
            return TaskStatus.skipped(
                f"Could not start proxy ({exc}). This may cause errors when Cargo tries to fetch dependencies. "
                "Please run `pipx install proxy.py; pipx inject proxy.py certifi`."
            )

        self.proxy_url.set(proxy_url)
        exit_stack.callback(lambda: self.proxy_url.clear())
        self.proxy_cert_file.set(cert_file)
        exit_stack.callback(lambda: self.proxy_cert_file.clear())

        # Make sure the proxy is alive for at least a certain amount of time to avoid a cryptic error message.
        self._start_time = time.perf_counter()
        exit_stack.callback(
            lambda: time.sleep(max(0, self.min_lifetime.get() - (time.perf_counter() - self._start_time)))
        )

        # Give the proxy some time to start up.
        time.sleep(self.startup_wait_time.get())

        exit_stack.enter_context(self._inject_config())
        return TaskStatus.started()
