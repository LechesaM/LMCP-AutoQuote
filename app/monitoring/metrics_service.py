from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_impl() -> ModuleType:
    module_path = Path(__file__).resolve().parents[2] / "lmcp-core" / "services" / "governance" / "metrics_service.py"
    spec = importlib.util.spec_from_file_location("lmcp_governance_metrics_service", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load governance metrics service from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()
reset_test_metrics = _IMPL.reset_test_metrics
increment_metric = _IMPL.increment_metric
get_metrics_snapshot = _IMPL.get_metrics_snapshot

__all__ = ["reset_test_metrics", "increment_metric", "get_metrics_snapshot"]
