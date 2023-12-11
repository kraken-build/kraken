"""
This module provides a thin client for the gitignore.io API to retrieve template `.gitignore` files.

Run this module to update the `gitignore-io-tokens.json.gz` file.
"""

import logging
from collections.abc import Sequence
from functools import lru_cache
from gzip import compress, decompress
from json import dumps, loads
from pathlib import Path
from typing import cast

from kraken.common import http

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
    "yarn",
    # Languages
    "c",
    "c++",
    "matlab",
    "node",
    "python",
    "react",
    "rust-analyzer",
    "rust",
]

# The file where we store the cached token data.
OUTPUT_FILE = Path(__file__).parent / "data" / "gitignore-io-tokens.json.gz"


def gitignore_io_fetch(tokens: Sequence[str]) -> str:
    """
    Fetch a `.gitignore` file from the gitignore.io API.
    """

    url = GITIGNORE_API_URL + ",".join(tokens)
    response = http.get(url)
    response.raise_for_status()
    return response.text.replace("\r\n", "\n")


def gitignore_io_fetch_cached(tokens: Sequence[str], backfill: bool) -> str:
    """
    Compile the `.gitignore` file for the given tokens from the cache. Any tokens that are not
    cached by be backfilled by making another request to gitignore.io if *backfill* is enabled.
    If *backfill* is disabled and a token is not cached, an #ValueError will be raised.
    """

    cache = load_token_cache()
    not_cached = set(tokens) - set(cache.keys())
    if not_cached and not backfill:
        raise ValueError(
            f"The following gitignore.io tokens are not distributed as part of kraken-std: {', '.join(not_cached)}"
            "\nBackfill is disabled, so this error is raised instead of making another HTTP request to "
            "gitignore.io."
        )

    additional_tokens = ""
    if not_cached:
        additional_tokens = gitignore_io_fetch([t for t in tokens if t in not_cached])  # Consistent order

    return "\n".join([cache[t] for t in tokens if t in cache] + [additional_tokens])


def write_token_cache(tokens: dict[str, str]) -> None:
    # NOTE(@NiklasRosenstein): We set mtime to 0 to ensure the Gzip compression result is stable.
    OUTPUT_FILE.write_bytes(compress(dumps(tokens).encode("utf-8"), mtime=0))


@lru_cache
def load_token_cache() -> dict[str, str]:
    if not OUTPUT_FILE.is_file():
        logger.warning("No gitignore.io token cache found at %s", OUTPUT_FILE)
        return {}
    return cast(dict[str, str], loads(decompress(OUTPUT_FILE.read_bytes()).decode("utf-8")))


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    result = {}
    for token in sorted(TOKENS):
        logger.info("Fetching token %s", token)
        result[token] = gitignore_io_fetch([token])

    write_token_cache(result)


if __name__ == "__main__":
    main()
