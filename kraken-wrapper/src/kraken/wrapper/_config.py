from __future__ import annotations

import logging
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, NamedTuple

import keyring
import keyring.backends.fail
import keyring.backends.null

from kraken.common import http
from kraken.common.http import ReadTimeout

logger = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path("~/.config/krakenw/config.toml").expanduser()


def type_fqn(x: type[Any] | object) -> str:
    if not isinstance(x, type):
        x = type(x)
    return f"{x.__module__}.{x.__name__}"


class AuthModel:
    """Provides an interface to store credentials safely in the system keyring. If keyring backend is available,
    the credentials are stored in the config file instead."""

    class CredentialsWithHost(NamedTuple):
        host: str
        username: str
        password: str

    class Credentials(NamedTuple):
        username: str
        password: str

    class CredentialCheck(NamedTuple):
        curl_command: str
        auth_check_result: bool
        raw_result: str
        hint: str

    def __init__(self, config: MutableMapping[str, Any], path: Path, use_keyring_if_available: bool) -> None:
        self._config = config
        self._path = path
        self._has_keyring = use_keyring_if_available and not isinstance(
            keyring.get_keyring(), (keyring.backends.fail.Keyring, keyring.backends.null.Keyring)
        )

    def get_credentials(self, host: str) -> Credentials | None:
        auth = self._config.get("auth", {})
        if host not in auth:
            return None
        username = auth[host].get("username")
        if not username:
            return None
        password = auth[host].get("password")
        if password is not None:
            return self.Credentials(username, password)
        if self._has_keyring:
            password = keyring.get_credential(host, username)
            if not password:
                return None
            return self.Credentials(username, password.password)
        return None

    def set_credentials(self, host: str, username: str, password: str) -> None:
        auth = self._config.setdefault("auth", {})
        auth[host] = {"username": username}
        if not self._has_keyring:
            auth[host]["password"] = password
            logger.warning(
                "no keyring backend available (%s), password will be stored in plain text",
                type_fqn(keyring.get_keyring()),
            )
            if isinstance(keyring.get_keyring(), keyring.backends.null.Keyring):
                logger.warning(
                    "it looks like you may have disabled keyring globally. consider re-enabling it by running `python "
                    "-m keyring diagnose` to find the config file and either removing the file entirely or removing "
                    "the `keyring.backends.null.Keyring` entry from the `default-backend` key in the `[backend]` "
                    "section. (the file is usually located at `~/.local/share/python_keyring/keyringrc.cfg` "
                    "or `~/.config/python_keyring/keyringrc.cfg`)"
                )
            logger.info("saving username and password for %s in %s", host, self._path)
        else:
            logger.debug("keyring backend available (%s)", type_fqn(keyring.get_keyring()))
            logger.info("saving username for %s in %s", host, self._path)
            logger.info("saving password for %s in keyring", host)
            keyring.set_password(host, username, password)

    def delete_credentials(self, host: str) -> None:
        auth = self._config.get("auth")
        if auth and host in auth:
            username = auth[host].get("username")
            logger.info("deleting username for %s from %s", host, self._path)
            del auth[host]
            if username and self._has_keyring:
                logger.info("deleting password for %s from keyring", host)
                try:
                    keyring.delete_password(host, username)
                except keyring.errors.PasswordDeleteError:
                    logger.warning("item in keychain not found")
        else:
            logger.warning("no credentials entry for %s", host)

    def list_credentials(self) -> list[CredentialsWithHost]:
        result = []
        for host in self._config.get("auth", {}):
            credentials = self.get_credentials(host)
            if credentials:
                result.append(self.CredentialsWithHost(host, *credentials))
        return result

    def check_credential(self, host: str, username: str, password: str) -> CredentialCheck | None:
        if "jfrog" in host:
            # Allow the user to override the url that will be used by setting
            # the `auth_check_url_suffix` in their krakenw/config.toml file PER HOST
            url_suffix = (
                self._config.get("auth", {})
                .get(host, {})
                .get("auth_check_url_suffix", "artifactory/api/pypi/python-all/simple/flask/")
            )
            url = f"https://{host}/{url_suffix}"
            curl_command = f"curl --user '{username}:{password}' {url}"

            # Get the result
            try:
                result = http.get(url, auth=(username, password), timeout=10)
            except ReadTimeout:
                logger.warning("HTTP Timeout when testing credentials")
                return None

            # Build hints
            hints = []

            if result.status_code == 401:
                if "Props authentication" in result.text:
                    hints.append("You may have used an API token rather than an identity token.")
                    hints.append("Your username and/or token may be incorrect.")
                elif "Token principal mismatch" in result.text:
                    hints.append("Your username and/or token may be incorrect.")
                elif "Bad credentials" in result.text:
                    hints.append("Your credentials are invalid")
                else:
                    hints.append("Credential check resulted in unknown 401 unauthorised error")
            elif result.status_code in (404, 302):
                hints.append(
                    f"Authentication URL incorrect (HTTP response {result.status_code}). "
                    f"Please check host.auth_check_url_suffix value in {self._path}"
                )

            return self.CredentialCheck(curl_command, result.status_code == 200, result.text, " ".join(hints))

        if "gitlab." in host:
            # Allow the user to override the url that will be used by setting
            # the `auth_check_url_suffix` in their krakenw/config.toml file PER HOST
            url_suffix = self._config.get("auth", {}).get(host, {}).get("auth_check_url_suffix", "api/v4/projects")
            url = f"https://{host}/{url_suffix}"

            # Get the result
            try:
                result = http.get(url, params={"access_token": password}, timeout=10)
            except ReadTimeout:
                logger.warning("HTTP Timeout when testing credentials")
                return None
            curl_command = "curl " + str(result.url)

            # Build hints
            hints = []
            if result.status_code == 401:
                hints.append("Your credentials are invalid")

            return self.CredentialCheck(curl_command, result.status_code == 200, result.text, " ".join(hints))

        return None
