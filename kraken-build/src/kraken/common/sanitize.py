import re


def sanitize_http_basic_auth(text: str, repl: str = "[MASKED]") -> str:
    """
    Sanitizes the *text* by replacing passwords in URLs with basic auth with *repl*.
    """

    # NOTE: This is slightly unsafe, `repl` could contain another group reference.
    return re.sub(r"(https?://[^\s]*?:)([^\s]+?)(@[^\s]+?)", r"\1" + repl + r"\3", text)
