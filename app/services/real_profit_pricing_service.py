from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "runtime"))
PRICING_DIR = RUNTIME_DIR / "real_profit_pricing"
PRICING_DIR.mkdir(parents=True, exist_ok=True)

LAST_FILE = PRICING_DIR / "last_pricing.json"
HISTORY_FILE = PRICING_DIR / "pricing_history.json"

MIN_PROFIT_REQUIRED = float(os.getenv("LMCP_MIN_PROFIT_REQUIRED", "30000"))
MIN_MARGIN_PERCENT = float(os.getenv("LMCP_MIN_MARGIN_PERCENT", "25"))
DEFAULT_TARGET_MARGIN_PERCENT = float(os.getenv("LMCP_TARGET_MARGIN_PERCENT", "35"))

EXCLUDED_KEYWORDS = [
    "medical", "pharmaceutical", "medicine", "surgical", "clinic", "hospital",
    "laptop", "computer", "printer", "server", "router", "software", "tablet",
    "petrol", "diesel", "fuel", "catering", "food", "refreshment",
]

STRICT_NON_SUPPLY_KEYWORDS = [
    "installation",
    "install",
    "contractor",
    "construction",
    "boq",
    "drawings",
    "fencing",
    "repair",
    "maintenance",
    "commission",
    "refurbishment",
    "civil works",
    "works",
]

SUPPLY_KEYWORDS = [
    "supply", "delivery", "stationery", "paper", "photocopy paper", "office supplies",
    "cleaning material", "ppe", "uniform", "furniture", "tools", "consumables",
    "toner", "cartridge", "printing", "protective clothing", "electrical material",
    "plumbing material", "building material",
]

CATEGORY_BASE_COSTS = {
    "photocopy paper": 220000,
    "paper": 160000,
    "stationery": 120000,
    "office supplies": 120000,
    "cleaning": 90000,
    "uniform": 180000,
    "ppe": 150000,
    "protective clothing": 150000,
    "furniture": 250000,
    "tools": 140000,
    "toner": 130000,
    "cartridge": 130000,
    "printing": 110000,
    "electrical": 180000,
    "plumbing": 160000,
    "building": 220000,
    "default_supply": 120000,
}


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _lower_blob(payload: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in [
        "buyer_rfq_number", "rfq_number", "reference_number", "title", "description",
        "category", "tender_category", "raw_text", "items", "line_items",
    ]:
        value = payload.get(key)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("R", "").replace(",", "").replace("%", "").strip()
        return float(value)
    except Exception:
        return default


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _append_history(item: Dict[str, Any], runtime_dir: Optional[str] = None) -> None:
    history_file = _resolve_runtime_path(HISTORY_FILE, runtime_dir)
    history = _read_json(history_file, [])
    if not isinstance(history, list):
        history = []
    history.append(item)
    _write_json(history_file, history[-1000:])


def _looks_excluded(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    blob = _lower_blob(payload)

    supply_delivery_only = any(
        phrase in blob
        for phrase in [
            "supply and delivery only",
            "supply & delivery only",
            "supply, delivery only",
            "supply and deliver only",
        ]
    )

    strict_hits: List[str] = []
    if not supply_delivery_only:
        strict_hits = []
        for kw in STRICT_NON_SUPPLY_KEYWORDS:
            if kw not in blob:
                continue

            # Do not treat explicit exclusions like "no installation" as scope.
            negated = any(
                phrase in blob
                for phrase in [
                    f"no {kw}",
                    f"without {kw}",
                    f"excluding {kw}",
                    f"not include {kw}",
                    f"does not include {kw}",
                ]
            )

            # Handles phrases like:
            # "No installation, construction, repair, maintenance..."
            no_idx = blob.find("no ")
            if not negated and no_idx >= 0:
                negation_window = blob[no_idx:no_idx + 140]
                if kw in negation_window:
                    negated = True

            if not negated:
                strict_hits.append(kw)

    normal_hits = [kw for kw in EXCLUDED_KEYWORDS if kw in blob]
    hits = strict_hits + [kw for kw in normal_hits if kw not in strict_hits]

    return bool(hits), hits


def _looks_supply(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    blob = _lower_blob(payload)
    hits = [kw for kw in SUPPLY_KEYWORDS if kw in blob]
    return bool(hits), hits


def _category_base_cost(payload: Dict[str, Any]) -> Tuple[float, str]:
    blob = _lower_blob(payload)
    for keyword, cost in CATEGORY_BASE_COSTS.items():
        if keyword != "default_supply" and keyword in blob:
            return float(cost), keyword
    return float(CATEGORY_BASE_COSTS["default_supply"]), "default_supply"


def _line_items_value(payload: Dict[str, Any]) -> float:
    total = 0.0
    items = payload.get("line_items") or payload.get("items") or []
    if not isinstance(items, list):
        return 0.0

    for item in items:
        if not isinstance(item, dict):
            continue
        line_total = (
            item.get("line_total")
            or item.get("total")
            or item.get("amount")
            or item.get("estimated_cost")
        )
        if line_total is not None:
            total += _to_float(line_total)
            continue

        qty = _to_float(item.get("quantity") or item.get("qty"), 0.0)
        unit = _to_float(item.get("unit_price") or item.get("price") or item.get("unit_cost"), 0.0)
        if qty > 0 and unit > 0:
            total += qty * unit

    return total


def _existing_profit_margin(payload: Dict[str, Any]) -> Tuple[float, float]:
    pricing = payload.get("pricing") or payload.get("pricing_summary") or {}
    if not isinstance(pricing, dict):
        pricing = {}

    profit = (
        payload.get("estimated_profit")
        or payload.get("total_profit")
        or payload.get("profit")
        or pricing.get("total_profit")
        or pricing.get("estimated_profit")
        or pricing.get("profit")
    )
    margin = (
        payload.get("estimated_margin_percent")
        or payload.get("estimated_margin_pct")
        or payload.get("achieved_margin_percent")
        or payload.get("margin_percent")
        or pricing.get("achieved_margin_percent")
        or pricing.get("margin_percent")
    )
    return _to_float(profit), _to_float(margin)


def enrich_with_real_profit_pricing(payload: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    payload = dict(payload or {})
    buyer_rfq = (
        payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("reference_number")
        or payload.get("title")
        or "UNKNOWN"
    )

    existing_profit, existing_margin = _existing_profit_margin(payload)
    excluded, excluded_hits = _looks_excluded(payload)
    supply_like, supply_hits = _looks_supply(payload)

    result: Dict[str, Any] = {
        "status": "started",
        "service_version": "LMCP_REAL_PROFIT_PRICING_V1",
        "buyer_rfq_number": buyer_rfq,
        "started_at": _now(),
        "existing_profit": existing_profit,
        "existing_margin_percent": existing_margin,
        "supply_like": supply_like,
        "supply_hits": supply_hits,
        "excluded": excluded,
        "excluded_hits": excluded_hits,
    }

    if excluded:
        result.update({
            "status": "skipped_excluded_category",
            "priced": False,
            "message": "Pricing skipped because excluded category keywords were detected.",
            "finished_at": _now(),
            "payload": payload,
        })
        last_file = _resolve_runtime_path(LAST_FILE, runtime_dir)
        _write_json(last_file, result)
        _append_history({k: v for k, v in result.items() if k != "payload"}, runtime_dir=runtime_dir)
        return result

    if not supply_like:
        result.update({
            "status": "skipped_not_supply_like",
            "priced": False,
            "message": "Pricing skipped because tender does not look like a supply-and-delivery opportunity.",
            "finished_at": _now(),
            "payload": payload,
        })
        last_file = _resolve_runtime_path(LAST_FILE, runtime_dir)
        _write_json(last_file, result)
        _append_history({k: v for k, v in result.items() if k != "payload"}, runtime_dir=runtime_dir)
        return result

    if existing_profit >= MIN_PROFIT_REQUIRED and existing_margin >= MIN_MARGIN_PERCENT:
        payload["estimated_profit"] = existing_profit
        payload["estimated_margin_percent"] = existing_margin
        result.update({
            "status": "ok",
            "priced": True,
            "method": "existing_pricing_already_meets_policy",
            "estimated_profit": existing_profit,
            "estimated_margin_percent": existing_margin,
            "finished_at": _now(),
            "payload": payload,
        })
        last_file = _resolve_runtime_path(LAST_FILE, runtime_dir)
        _write_json(last_file, result)
        _append_history({k: v for k, v in result.items() if k != "payload"}, runtime_dir=runtime_dir)
        return result

    item_value = _line_items_value(payload)
    category_cost, category = _category_base_cost(payload)
    estimated_cost = max(item_value, category_cost)

    target_margin = max(DEFAULT_TARGET_MARGIN_PERCENT, MIN_MARGIN_PERCENT)
    target_profit_from_margin = estimated_cost * (target_margin / 100.0)

    target_profit = max(MIN_PROFIT_REQUIRED, target_profit_from_margin)
    sell_excl_vat = estimated_cost + target_profit
    achieved_margin = (target_profit / sell_excl_vat) * 100 if sell_excl_vat > 0 else 0.0

    # If margin falls below minimum because profit floor is too small for cost, lift selling price to satisfy margin.
    if achieved_margin < MIN_MARGIN_PERCENT:
        sell_excl_vat = estimated_cost / (1 - (MIN_MARGIN_PERCENT / 100.0))
        target_profit = sell_excl_vat - estimated_cost
        achieved_margin = (target_profit / sell_excl_vat) * 100 if sell_excl_vat > 0 else 0.0

    vat = sell_excl_vat * 0.15
    sell_incl_vat = sell_excl_vat + vat

    payload["estimated_profit"] = round(target_profit, 2)
    payload["estimated_margin_percent"] = round(achieved_margin, 2)
    payload["pricing_summary"] = {
        "currency": "ZAR",
        "pricing_mode": "real_profit_fallback",
        "category": category,
        "total_cost_excl_vat": round(estimated_cost, 2),
        "total_sell_excl_vat": round(sell_excl_vat, 2),
        "total_vat": round(vat, 2),
        "total_sell_incl_vat": round(sell_incl_vat, 2),
        "total_profit": round(target_profit, 2),
        "achieved_margin_percent": round(achieved_margin, 2),
        "minimum_profit_required": MIN_PROFIT_REQUIRED,
        "minimum_margin_percent": MIN_MARGIN_PERCENT,
        "target_margin_percent": target_margin,
    }

    if not payload.get("line_items"):
        payload["line_items"] = [
            {
                "description": payload.get("title") or "Supply and delivery items",
                "quantity": 1,
                "unit": "lot",
                "unit_cost": round(estimated_cost, 2),
                "unit_price": round(sell_excl_vat, 2),
                "line_total": round(sell_excl_vat, 2),
            }
        ]

    result.update({
        "status": "ok",
        "priced": True,
        "method": "real_profit_fallback",
        "category": category,
        "estimated_cost": round(estimated_cost, 2),
        "estimated_profit": payload["estimated_profit"],
        "estimated_margin_percent": payload["estimated_margin_percent"],
        "finished_at": _now(),
        "payload": payload,
    })

    last_file = _resolve_runtime_path(LAST_FILE, runtime_dir)
    _write_json(last_file, result)
    _append_history({k: v for k, v in result.items() if k != "payload"}, runtime_dir=runtime_dir)
    return result


def get_real_profit_pricing_status(limit: int = 20, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    history_file = _resolve_runtime_path(HISTORY_FILE, runtime_dir)
    last_file = _resolve_runtime_path(LAST_FILE, runtime_dir)
    history = _read_json(history_file, [])
    if not isinstance(history, list):
        history = []
    return {
        "status": "ok",
        "service_version": "LMCP_REAL_PROFIT_PRICING_V1",
        "last": _read_json(last_file, {}),
        "recent": history[-limit:],
        "settings": {
            "minimum_profit_required": MIN_PROFIT_REQUIRED,
            "minimum_margin_percent": MIN_MARGIN_PERCENT,
            "default_target_margin_percent": DEFAULT_TARGET_MARGIN_PERCENT,
        },
        "files": {
            "last": str(last_file),
            "history": str(history_file),
            "runtime_dir": str(_resolve_runtime_path(PRICING_DIR, runtime_dir)),
        },
        "updated_at": _now(),
    }
