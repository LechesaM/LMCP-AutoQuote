from typing import Any, Dict

from app.core.system_guard import run_system_guard


def run_self_check() -> Dict[str, Any]:
    """
    Single entrypoint for internal full-system verification.
    """
    return run_system_guard()
