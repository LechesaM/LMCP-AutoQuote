from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_impl() -> ModuleType:
    module_path = Path(__file__).resolve().parents[2] / "lmcp-core" / "services" / "intelligence" / "amount_quantity_integrity_validation_engine.py"
    spec = importlib.util.spec_from_file_location("lmcp_intelligence_amount_quantity_integrity_validation_engine", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load intelligence amount/quantity validation engine from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()

validate_amount_quantity_integrity = _IMPL.validate_amount_quantity_integrity
validate_amount_quantity_integrity_for_table = _IMPL.validate_amount_quantity_integrity_for_table

__all__ = [
    "validate_amount_quantity_integrity",
    "validate_amount_quantity_integrity_for_table",
]
