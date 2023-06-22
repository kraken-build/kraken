"""
This module provides a thin client for the gitignore.io API to retrieve template `.gitignore` files.
We use it to regenerate the `gitignore-io-tokens.json` file that the `kraken-std` package ships with,
avoiding requests to `gitignore.io` at build time.
"""

import logging
from gzip import compress, decompress
from json import dumps, loads
from pathlib import Path
from typing import Sequence

from kraken.std import http

logger = logging.getLogger(__name__)


GITIGNORE_API_URL = "https://www.toptal.com/developers/gitignore/api/"

# When running this script, these tokens will be fetched and written into a local cache file.
# When these tokens are requested, we don't need to make a request to gitignore.io at build time.
TOKENS = [
    # Platforms
    "linux",
    "macos",
    "windows",
    # IDEs
    "clion",
    "emacs",
    "intellij",
    "jupyternotebooks",
    "pycharm",
    "vim",
    "visualstudiocode",
    # Tooling
    "gcov",
    "git",
    "node",
    "yarn",
]

# The file where we store the cached token data.
OUTPUT_FILE = Path(__file__).parent / "data" / "gitignore-io-tokens.json.gz"


def get_gitignore(tokens: Sequence[str]) -> None:
    """
    Fetch a `.gitignore` file from the gitignore.io API.
    """

    url = GITIGNORE_API_URL + ",".join(tokens)
    response = http.get(url)
    response.raise_for_status()
    return response.text.replace("\r\n", "\n")


def write_token_cache(tokens: dict[str, str]) -> None:
    OUTPUT_FILE.write_bytes(compress(dumps(tokens).encode("utf-8")))


def load_token_cache() -> dict[str, str]:
    if not OUTPUT_FILE.is_file():
        logger.warning("No gitignore.io token cache found at %s", OUTPUT_FILE)
        return {}
    return loads(decompress(OUTPUT_FILE.read_bytes()).decode("utf-8"))


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    result = {}
    for token in sorted(TOKENS):
        logger.info("Fetching token %s", token)
        result[token] = get_gitignore([token])

    write_token_cache(result)


if __name__ == "__main__":
    main()
