from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json
import math
import re


ENGINE_VERSION = "REAL_BUYER_PRICING_ENGINE_V1"

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "real_buyer_pricing_engine"
REPORT_DIR = RUNTIME_DIR / "reports"

VAT_RATE = 0.15
DEFAULT_TARGET_MARGIN_PERCENT = 25.0
DEFAULT_MINIMUM_PROFIT_REQUIRED = 30000.0

VERIFIED_QUANTITY_SOURCES = {
    "buyer_docx_main_document",
    "buyer_boq_extraction",
}

BLOCKED_QUANTITY_SOURCES = {
    "",
    "unverified",
    "synthetic",
    "fallback",
    "strategic_profit_floor_fallback",
}

CONSERVATIVE_COST_BANDS = [
    {
        "name": "steel_drum_160l",
        "keywords": ["160l", "160 l", "metal", "drum"],
        "unit_cost_excl_vat": 590.0,
        "confidence": 0.58,
    },
    {
        "name": "steel_drum_100l",
        "keywords": ["100 litre", "100l", "100 l", "drum"],
        "unit_cost_excl_vat": 470.0,
        "confidence": 0.56,
    },
    {
        "name": "steel_drum_210l",
        "keywords": ["210 l", "210l", "metal", "drum"],
        "unit_cost_excl_vat": 720.0,
        "confidence": 0.58,
    },
    {
        "name": "generic_steel_drum",
        "keywords": ["drum", "metal"],
        "unit_cost_excl_vat": 650.0,
        "confidence": 0.50,
    },
    {
        "name": "generic_supply_item",
        "keywords": [],
        "unit_cost_excl_vat": 250.0,
        "confidence": 0.35,
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    try:
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            value = float(value)
            if math.isnan(value) or math.isinf(value):
                return default
            return value
        cleaned = str(value).replace(",", "").replace("R", "").replace("r", "").strip()
        cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
        if not cleaned or cleaned in {"-", ".", "-."}:
            return default
        return float(cleaned)
    except Exception:
        return default


def _slug(value: Any, limit: int = 120) -> str:
    text = _safe_str(value)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return (text[:limit].strip("-") or "real-buyer-pricing")


def _ensure_dirs() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _round_money(value: float) -> float:
    return round(float(value or 0.0), 2)


def _extract_verified_line_items(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(item, dict):
        return []

    candidates = item.get("line_items")
    if not isinstance(candidates, list) or not candidates:
        candidates = item.get("items")

    if not isinstance(candidates, list):
        return []

    out: List[Dict[str, Any]] = []
    for row in candidates:
        if not isinstance(row, dict):
            continue

        description = _safe_str(row.get("description"))
        quantity = _to_float(row.get("quantity"), 0.0)
        unit = _safe_str(row.get("unit") or "Each") or "Each"

        if not description or quantity <= 0:
            continue

        source = _safe_str(row.get("source") or item.get("quantity_source"))
        if source and source not in VERIFIED_QUANTITY_SOURCES:
            continue

        out.append({
            "line_number": _safe_str(row.get("line_number") or row.get("item_code") or len(out) + 1),
            "description": description,
            "quantity": quantity,
            "unit": unit,
            "item_code": _safe_str(row.get("item_code")),
            "specification": _safe_str(row.get("specification")),
            "source": source or _safe_str(item.get("quantity_source")),
            "evidence": row.get("evidence") if isinstance(row.get("evidence"), list) else [],
        })

    return out


def _match_cost_band(description: str) -> Dict[str, Any]:
    desc = _safe_lower(description)

    best = CONSERVATIVE_COST_BANDS[-1]
    best_score = -1

    for band in CONSERVATIVE_COST_BANDS:
        keywords = band.get("keywords") or []
        if not keywords:
            continue

        score = sum(1 for kw in keywords if _safe_lower(kw) in desc)
        if score > best_score:
            best = band
            best_score = score

    if best_score <= 0:
        best = CONSERVATIVE_COST_BANDS[-1]

    return dict(best)


def _calculate_sell_from_margin(unit_cost_excl_vat: float, target_margin_percent: float) -> float:
    margin = max(0.0, min(float(target_margin_percent or 0.0), 80.0)) / 100.0
    if margin >= 1:
        margin = 0.25
    return unit_cost_excl_vat / (1.0 - margin)


def _price_line_item(row: Dict[str, Any], target_margin_percent: float) -> Dict[str, Any]:
    quantity = _to_float(row.get("quantity"), 0.0)
    cost_band = _match_cost_band(row.get("description", ""))

    unit_cost_excl_vat = _to_float(cost_band.get("unit_cost_excl_vat"), 0.0)
    unit_sell_excl_vat = _calculate_sell_from_margin(unit_cost_excl_vat, target_margin_percent)

    total_cost_excl_vat = unit_cost_excl_vat * quantity
    total_sell_excl_vat = unit_sell_excl_vat * quantity
    total_vat = total_sell_excl_vat * VAT_RATE
    total_sell_incl_vat = total_sell_excl_vat + total_vat
    profit = total_sell_excl_vat - total_cost_excl_vat
    actual_margin = (profit / total_sell_excl_vat * 100.0) if total_sell_excl_vat else 0.0

    confidence = _to_float(cost_band.get("confidence"), 0.35)

    return {
        "line_number": row.get("line_number"),
        "item_code": row.get("item_code", ""),
        "description": row.get("description", ""),
        "specification": row.get("specification", ""),
        "quantity": quantity,
        "unit": row.get("unit", "Each"),
        "quantity_source": row.get("source", ""),
        "pricing_source": "conservative_market_estimate",
        "supplier_quote_verified": False,
        "supplier_sourcing_status": "supplier_quote_required",
        "cost_band": cost_band.get("name"),
        "unit_cost_excl_vat": _round_money(unit_cost_excl_vat),
        "unit_sell_excl_vat": _round_money(unit_sell_excl_vat),
        "unit_sell_incl_vat": _round_money(unit_sell_excl_vat * (1.0 + VAT_RATE)),
        "total_cost_excl_vat": _round_money(total_cost_excl_vat),
        "total_sell_excl_vat": _round_money(total_sell_excl_vat),
        "total_vat": _round_money(total_vat),
        "total_sell_incl_vat": _round_money(total_sell_incl_vat),
        "profit_estimate": _round_money(profit),
        "margin_percent": round(actual_margin, 2),
        "confidence": confidence,
        "evidence": row.get("evidence", []),
        "pricing_warning": (
            "No supplier quote verified. Conservative market estimate used for controlled operator review only."
        ),
    }


def _validate_pricing_input(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "pricing_safe": False,
            "pricing_block_reason": "invalid_item_payload",
        }

    quantity_source = _safe_str(item.get("quantity_source"))
    requires_quantity_verification = bool(item.get("requires_quantity_verification"))
    boq_line_item_count = int(_to_float(item.get("boq_line_item_count"), 0.0))

    if quantity_source in BLOCKED_QUANTITY_SOURCES:
        return {
            "pricing_safe": False,
            "pricing_block_reason": f"blocked_quantity_source:{quantity_source or 'missing'}",
        }

    if quantity_source not in VERIFIED_QUANTITY_SOURCES:
        return {
            "pricing_safe": False,
            "pricing_block_reason": f"unsupported_quantity_source:{quantity_source}",
        }

    if requires_quantity_verification:
        return {
            "pricing_safe": False,
            "pricing_block_reason": "requires_quantity_verification",
        }

    if boq_line_item_count <= 0:
        return {
            "pricing_safe": False,
            "pricing_block_reason": "no_verified_boq_line_items",
        }

    verified_items = _extract_verified_line_items(item)
    if not verified_items:
        return {
            "pricing_safe": False,
            "pricing_block_reason": "no_verified_line_items_available",
        }

    return {
        "pricing_safe": True,
        "pricing_block_reason": "",
        "verified_line_items": verified_items,
    }


def price_verified_rfq(
    item: Dict[str, Any],
    minimum_profit_required: float = DEFAULT_MINIMUM_PROFIT_REQUIRED,
    target_margin_percent: float = DEFAULT_TARGET_MARGIN_PERCENT,
) -> Dict[str, Any]:
    _ensure_dirs()

    if not isinstance(item, dict):
        item = {}

    title = _safe_str(item.get("title") or item.get("buyer_rfq_number") or "rfq")
    validation = _validate_pricing_input(item)

    if not validation.get("pricing_safe"):
        result = {
            "status": "blocked",
            "engine_version": ENGINE_VERSION,
            "priced_at": _now_iso(),
            "title": title,
            "buyer_name": _safe_str(item.get("buyer_name")),
            "buyer_rfq_number": _safe_str(item.get("buyer_rfq_number")),
            "reference_number": _safe_str(item.get("reference_number") or item.get("rfq_number")),
            "pricing_safe": False,
            "pricing_block_reason": validation.get("pricing_block_reason", "pricing_input_not_safe"),
            "priced_line_items": [],
            "pricing_summary": {
                "line_count": 0,
                "total_cost_excl_vat": 0.0,
                "total_sell_excl_vat": 0.0,
                "total_vat": 0.0,
                "total_sell_incl_vat": 0.0,
                "total_profit": 0.0,
                "margin_percent": 0.0,
                "minimum_profit_required": float(minimum_profit_required),
                "target_margin_percent": float(target_margin_percent),
                "vat_rate_percent": VAT_RATE * 100.0,
                "meets_minimum_profit_required": False,
            },
            "supplier_quote_required": True,
            "confidence": 0.0,
        }
        report_path = REPORT_DIR / f"{_slug(title)}__real_buyer_pricing_report.json"
        report_path.write_text(json.dumps(result, indent=2, default=str))
        result["report_path"] = str(report_path)
        return result

    verified_items = validation.get("verified_line_items") or []
    priced_line_items = [
        _price_line_item(row, target_margin_percent=target_margin_percent)
        for row in verified_items
    ]

    total_cost_excl_vat = sum(_to_float(x.get("total_cost_excl_vat")) for x in priced_line_items)
    total_sell_excl_vat = sum(_to_float(x.get("total_sell_excl_vat")) for x in priced_line_items)
    total_vat = sum(_to_float(x.get("total_vat")) for x in priced_line_items)
    total_sell_incl_vat = sum(_to_float(x.get("total_sell_incl_vat")) for x in priced_line_items)
    total_profit = sum(_to_float(x.get("profit_estimate")) for x in priced_line_items)

    margin_percent = (total_profit / total_sell_excl_vat * 100.0) if total_sell_excl_vat else 0.0
    avg_confidence = (
        sum(_to_float(x.get("confidence")) for x in priced_line_items) / max(len(priced_line_items), 1)
        if priced_line_items else 0.0
    )

    supplier_quote_required = any(not bool(x.get("supplier_quote_verified")) for x in priced_line_items)
    meets_minimum_profit = total_profit >= float(minimum_profit_required or 0.0)

    pricing_safe = bool(priced_line_items)
    pricing_block_reason = ""
    if not meets_minimum_profit:
        pricing_safe = False
        pricing_block_reason = "estimated_profit_below_minimum_required"

    result = {
        "status": "ok" if pricing_safe else "review_required",
        "engine_version": ENGINE_VERSION,
        "priced_at": _now_iso(),
        "title": title,
        "buyer_name": _safe_str(item.get("buyer_name")),
        "buyer_rfq_number": _safe_str(item.get("buyer_rfq_number")),
        "reference_number": _safe_str(item.get("reference_number") or item.get("rfq_number")),
        "quantity_source": _safe_str(item.get("quantity_source")),
        "verified_quantity_source_path": _safe_str(item.get("verified_quantity_source_path")),
        "pricing_safe": pricing_safe,
        "pricing_block_reason": pricing_block_reason,
        "priced_line_items": priced_line_items,
        "pricing_summary": {
            "line_count": len(priced_line_items),
            "total_cost_excl_vat": _round_money(total_cost_excl_vat),
            "total_sell_excl_vat": _round_money(total_sell_excl_vat),
            "total_vat": _round_money(total_vat),
            "total_sell_incl_vat": _round_money(total_sell_incl_vat),
            "total_profit": _round_money(total_profit),
            "margin_percent": round(margin_percent, 2),
            "minimum_profit_required": float(minimum_profit_required),
            "target_margin_percent": float(target_margin_percent),
            "vat_rate_percent": VAT_RATE * 100.0,
            "meets_minimum_profit_required": bool(meets_minimum_profit),
            "pricing_source": "conservative_market_estimate",
            "supplier_quote_verified": False,
        },
        "supplier_quote_required": bool(supplier_quote_required),
        "confidence": round(avg_confidence, 4),
        "operator_review_required": True,
        "controlled_mode_only": True,
        "warnings": [
            "Pricing is based on verified buyer quantities.",
            "Supplier quotes are not yet verified.",
            "Use this as controlled-mode pricing until supplier confirmation is attached.",
        ],
    }

    report_path = REPORT_DIR / f"{_slug(title)}__real_buyer_pricing_report.json"
    report_path.write_text(json.dumps(result, indent=2, default=str))
    result["report_path"] = str(report_path)

    return result


def price_rfq(item: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    return price_verified_rfq(item, **kwargs)


def get_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "runtime_dir": str(RUNTIME_DIR),
        "report_dir": str(REPORT_DIR),
        "minimum_profit_required": DEFAULT_MINIMUM_PROFIT_REQUIRED,
        "target_margin_percent": DEFAULT_TARGET_MARGIN_PERCENT,
        "vat_rate_percent": VAT_RATE * 100.0,
        "capabilities": [
            "verified_quantity_only_pricing",
            "blocks_unverified_quantities",
            "blocks_synthetic_fallback_items",
            "conservative_market_estimate",
            "supplier_quote_required_flag",
            "vat_15_percent",
            "profit_estimate",
            "minimum_profit_enforcement",
            "pricing_report_json",
            "controlled_mode_only",
        ],
    }
