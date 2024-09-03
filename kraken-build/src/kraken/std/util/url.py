from urllib.parse import urlparse


def redact_url_password(url: str, placeholder: str = "[REDACTED]") -> str:
    """Redacts the password in a URL with the given placeholder, if any."""

    parsed = urlparse(url)
    if parsed.password:
        return parsed._replace(netloc=f"{parsed.username}:{placeholder}@{parsed.hostname}").geturl()
    return url


def inject_url_credentials(url: str, username: str, password: str) -> str:
    """Injects a username and password into a URL."""

    parsed = urlparse(url)
    replaced = parsed._replace(netloc=f"{username}:{password}@{parsed.netloc}")
    return replaced.geturl()
