from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_impl() -> ModuleType:
    module_path = Path(__file__).resolve().parents[2] / "lmcp-core" / "services" / "governance" / "health_service.py"
    spec = importlib.util.spec_from_file_location("lmcp_governance_health_service", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load governance health service from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()
get_system_health = _IMPL.get_system_health

__all__ = ["get_system_health"]
