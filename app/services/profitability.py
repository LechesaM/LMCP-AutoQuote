from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_impl() -> ModuleType:
    module_path = Path(__file__).resolve().parents[2] / "lmcp-core" / "services" / "commercial" / "profitability.py"
    spec = importlib.util.spec_from_file_location("lmcp_commercial_profitability", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load commercial profitability helper from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()

to_float = _IMPL.to_float
calculate_profitability = _IMPL.calculate_profitability
profitability_decision = _IMPL.profitability_decision
extract_cost_and_revenue_from_pricing_result = _IMPL.extract_cost_and_revenue_from_pricing_result
evaluate_pricing_result_profitability = _IMPL.evaluate_pricing_result_profitability

__all__ = [
    "to_float",
    "calculate_profitability",
    "profitability_decision",
    "extract_cost_and_revenue_from_pricing_result",
    "evaluate_pricing_result_profitability",
]
