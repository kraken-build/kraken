from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, MutableMapping, NamedTuple

import keyring
import keyring.backends.fail

logger = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path("~/.config/krakenw/config.toml").expanduser()


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

    def __init__(self, config: MutableMapping[str, Any], path: Path) -> None:
        self._config = config
        self._path = path
        self._has_keyring = not isinstance(keyring.get_keyring(), keyring.backends.fail.Keyring)

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
            logger.warning("no keyring backend available, password will be stored in plain text")
            logger.info("saving username and password for %s in %s", host, self._path)
        else:
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
