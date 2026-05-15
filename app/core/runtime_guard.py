import logging
from functools import wraps
from typing import Any, Callable


logger = logging.getLogger(__name__)


def guarded_service(service_name: str) -> Callable:
    """
    Prevent one service failure from crashing the whole flow.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.exception("GUARDED_SERVICE failure in %s: %s", service_name, exc)
                return None
        return wrapper
    return decorator
