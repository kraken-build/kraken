import ast
from pathlib import Path

from kraken.common.http.lint_ban_bare_requests import BanBareHttpxCalls, BanBareRequestsCalls

DATA_PATH = Path(__file__).parent / "data"


def test_lint() -> None:
    lints = lint_file("http_requests.py")
    assert lints == (1, 2)


def lint_file(filename: str) -> tuple[int, int]:
    filepath = (DATA_PATH / filename).absolute()
    with open(filepath) as f:
        tree = ast.parse(f.read())

    httpx = list(BanBareHttpxCalls(tree, str(filepath)).run())
    requests = list(BanBareRequestsCalls(tree, str(filepath)).run())

    return (len(httpx), len(requests))
