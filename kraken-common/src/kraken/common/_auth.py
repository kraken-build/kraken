from typing import NamedTuple


class CredentialsWithHost(NamedTuple):
    host: str
    username: str
    password: str
