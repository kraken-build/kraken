import ast

from kraken.common.http.lint_ban_bare_requests import BanBareHttpxCalls, BanBareRequestsCalls

from tests.resources import data_path


def test_lint() -> None:
    lints = lint_file("http_requests.py")
    assert lints == (1, 2)


def lint_file(filename: str) -> tuple[int, int]:
    filepath = data_path(filename)
    with open(filepath) as f:
        tree = ast.parse(f.read())

    httpx = list(BanBareHttpxCalls(tree, str(filepath)).run())
    requests = list(BanBareRequestsCalls(tree, str(filepath)).run())

    return (len(httpx), len(requests))
