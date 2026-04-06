import importlib
import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


def safe_import(module_path: str, attr_name: Optional[str] = None, default: Any = None) -> Any:
    """
    Safely import a module or attribute without crashing the system.
    """
    try:
        module = importlib.import_module(module_path)
        if attr_name:
            return getattr(module, attr_name, default)
        return module
    except Exception as exc:
        logger.warning("SAFE_IMPORT failed: %s (%s)", module_path, exc)
        return default
