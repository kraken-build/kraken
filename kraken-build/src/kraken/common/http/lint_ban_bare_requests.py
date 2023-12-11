# A linter that ensures every HTTP request goes through this 'http' module, instead of using httpx or requests directly

from __future__ import annotations

import ast
from collections.abc import Generator

from . import __all__ as WRAPPED_HTTP_FUNCTIONS

HTTPX_ERROR_CODE = "KRA001"

PLAIN_HTTPX_MESSAGE = f"""{HTTPX_ERROR_CODE} using `httpx` directly is disallowed, because it may not play well with
corporate proxies.
Use kraken.common.http instead (which wraps calls to httpx).

See https://github.com/kraken-build/kraken-std/pull/132
"""

REQUESTS_ERROR_CODE = "KRA002"

PLAIN_REQUESTS_MESSAGE = f"""{REQUESTS_ERROR_CODE} using `requests` directly is disallowed, because it may not play well
with corporate proxies (unless `pip-system-certs` is installed).
Use kraken.common.http instead (which wraps calls to httpx).

See https://github.com/kraken-build/kraken-std/pull/132
"""


class BareCallsVisitor(ast.NodeVisitor):
    def __init__(self, disallowed_module: str) -> None:
        self.bare_calls: list[ast.AST] = []
        self.disallowed_module = disallowed_module

    def visit_Call(self, node: ast.Call) -> None:
        if BareCallsVisitor.call_is_bare(node, self.disallowed_module):
            self.bare_calls.append(node)

    @classmethod
    def call_is_bare(cls, call: ast.Call, disallowed_module: str) -> bool:
        """
        We don't want to forbid 'import httpx', because we may still want to use e.g. error codes from there
        Let's only forbid calls to functions that are wrapped by our http module
        """
        fn = call.func
        return (
            getattr(fn, "attr", None) in WRAPPED_HTTP_FUNCTIONS
            and hasattr(fn, "value")
            and BareCallsVisitor.call_is_from_disallowed_module(fn.value, disallowed_module)
        )

    @classmethod
    def call_is_from_disallowed_module(cls, fn_value: ast.expr, disallowed_module: str) -> bool:
        if getattr(fn_value, "attr", None) == disallowed_module:
            return hasattr(fn_value, "value") and BareCallsVisitor.call_is_from_disallowed_module(
                fn_value.value, disallowed_module
            )

        return getattr(fn_value, "id", None) == disallowed_module


class BanBareCalls:
    """
    Detects occurences of bare httpx or requests function calls.
    These are discouraged, as using the corresponding calls from the kraken.common.http usually work better
    in corporate networks.
    """

    def __init__(
        self, tree: ast.AST, filename: str, disallowed_module: str, error_message: str, final_type: type
    ) -> None:
        self.tree = tree
        self.disallowed_module = disallowed_module
        self.error_message = error_message
        self.final_type = final_type

    def run(self) -> Generator[tuple[int, int, str, type[BanBareHttpxCalls | BanBareRequestsCalls]], None, None]:
        visitor = BareCallsVisitor(self.disallowed_module)
        visitor.visit(self.tree)

        for node in visitor.bare_calls:
            yield node.lineno, node.col_offset, self.error_message, self.final_type


class BanBareHttpxCalls(BanBareCalls):
    def __init__(self, tree: ast.AST, filename: str) -> None:
        super().__init__(tree, filename, "httpx", PLAIN_HTTPX_MESSAGE, type(self))


class BanBareRequestsCalls(BanBareCalls):
    def __init__(self, tree: ast.AST, filename: str) -> None:
        super().__init__(tree, filename, "requests", PLAIN_REQUESTS_MESSAGE, type(self))
