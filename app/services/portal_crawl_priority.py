from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_impl() -> ModuleType:
    module_path = Path(__file__).resolve().parents[2] / "lmcp-core" / "services" / "acquisition" / "portal_crawl_priority.py"
    spec = importlib.util.spec_from_file_location("lmcp_acquisition_portal_crawl_priority", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load acquisition portal crawl priority from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()
get_default_historical_stats = _IMPL.get_default_historical_stats
get_priority_portal_queue = _IMPL.get_priority_portal_queue
choose_portals_for_harvest = _IMPL.choose_portals_for_harvest

__all__ = ["get_default_historical_stats", "get_priority_portal_queue", "choose_portals_for_harvest"]
