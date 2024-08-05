import logging
import sys
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)


T_Callable = TypeVar("T_Callable", bound=Callable[..., Any])


def exit_on_known_exceptions(
    *exception_types: type[BaseException], log: bool = True, exit_code: int = 1
) -> Callable[[T_Callable], T_Callable]:
    """
    A useful decorator for CLI entrypoints that catches known exceptions and exits with a non-zero exit code.
    """

    def decorator(func: T_Callable) -> T_Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exception_types:
                if log:
                    logger.debug("Exiting due to known exception", exc_info=True)
                sys.exit(exit_code)

        return wrapper  # type: ignore[return-value]

    return decorator
