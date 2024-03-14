from urllib.parse import urlparse


def redact_url_password(url: str, placeholder: str = "[REDACTED]") -> str:
    """Redacts the password in a URL with the given placeholder, if any."""

    parsed = urlparse(url)
    replaced = parsed._replace(netloc=f"{parsed.username}:{placeholder}@{parsed.hostname}")
    return replaced.geturl()
