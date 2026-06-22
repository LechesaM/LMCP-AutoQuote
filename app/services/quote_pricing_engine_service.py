from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_impl() -> ModuleType:
    module_path = Path(__file__).resolve().parents[2] / "lmcp-core" / "services" / "commercial" / "quote_pricing_engine_service.py"
    spec = importlib.util.spec_from_file_location("lmcp_commercial_quote_pricing_engine_service", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load commercial quote pricing engine from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()

price_buyer_schedule_rows = _IMPL.price_buyer_schedule_rows
attach_quote_pricing_to_record = _IMPL.attach_quote_pricing_to_record

__all__ = ["price_buyer_schedule_rows", "attach_quote_pricing_to_record"]
