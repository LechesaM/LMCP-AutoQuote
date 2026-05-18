from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import re
import traceback

SERVICE_VERSION = "V43_AUTO_PRICING_ENGINE_V43_1_STRICT_QUANTITY"
DEFAULT_OUTPUT_DIR = Path("runtime/auto_pricing_v43")

DEFAULT_MARGIN_PERCENT = 25.0
DEFAULT_PROFIT_FLOOR = 30000.0
DEFAULT_VAT_RATE = 15.0

MAX_ACCEPTED_QUANTITY = 1000.0

FALSE_POSITIVE_TERMS = [
    "evaluation", "functionality", "80:20", "90/10", "specific goals",
    "preference points", "medical certificate", "director", "csd full report",
    "telephone", "contact person", "closing date", "submission",
    "declaration", "sbd", "bidder", "tax compliance", "world heritage",
    "government gazette", "hectares", "ocean", "mozambican border",
    "competitor", "collusive", "quality, quantity, specifications",
    "number of points", "mode of confirmation", "proof to be submitted",
]

REAL_ITEM_HINTS = [
    "notebook", "notebooks", "pen", "pens", "shirt", "shirts", "t-shirt",
    "tshirts", "t shirts", "golf shirt", "fabric", "branded item",
    "logo", "branded", "pack", "gift", "corporate gift", "bags", "cap",
    "bottle", "mug", "diary", "lanyard", "usb", "clothing",
]

CATEGORY_PRICING = {
    "notebook": {"unit_cost": 55.00, "unit": "each", "description": "Branded notebook with full-colour logo"},
    "pen": {"unit_cost": 12.00, "unit": "each", "description": "Branded black pen with full-colour logo"},
    "shirt": {"unit_cost": 145.00, "unit": "each", "description": "Branded clothing item / shirt with logo"},
    "tshirt": {"unit_cost": 135.00, "unit": "each", "description": "Branded T-shirt with logo"},
    "clothing": {"unit_cost": 145.00, "unit": "each", "description": "Branded clothing item with logo"},
    "gift_pack": {"unit_cost": 245.00, "unit": "pack", "description": "Corporate branded gift pack"},
    "generic": {"unit_cost": 100.00, "unit": "each", "description": "Supply and delivery item"},
}


@dataclass
class AutoPricedLineItem:
    item_no: int
    description: str
    original_description: str
    quantity: float
    unit: str
    estimated_unit_cost_excl_vat: float
    margin_percent: float
    unit_price_excl_vat: float
    total_excl_vat: float
    vat_rate_percent: float
    vat_amount: float
    total_incl_vat: float
    currency: str
    pricing_method: str
    confidence: float
    source_page: Optional[int]
    reason: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ").replace("\u00a0", " ")).strip()


def _money(value: float) -> float:
    return round(float(value), 2)


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _has_real_item_hint(text: str) -> bool:
    t = _normalise_text(text).lower()
    return any(h in t for h in REAL_ITEM_HINTS)


def _looks_like_date_or_reference_number(text: str) -> bool:
    t = _normalise_text(text).lower()

    if re.search(r"\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b", t):
        return True

    if re.search(r"\b(19|20)\d{2}\b", t) and not _has_real_item_hint(t):
        return True

    if re.search(r"\bnotice\s+number\b|\bgovernment\s+gazette\b|\bregulation\b", t):
        return True

    return False


def _looks_false_positive(text: str) -> bool:
    t = _normalise_text(text).lower()
    if not t:
        return True

    if re.search(r"\b0\d{2}\s*\d{3}\s*\d{4}\b", t):
        return True

    if _looks_like_date_or_reference_number(t):
        return True

    if any(term in t for term in FALSE_POSITIVE_TERMS):
        if not _has_real_item_hint(t):
            return True

    if len(t) > 420 and not _has_real_item_hint(t):
        return True

    if re.search(r"\br\s*30\s*000\b|\br1\s*000\s*000\b|r\s*1\s*000\s*000", t):
        return True

    if "hectares" in t or "world heritage" in t:
        return True

    return False


def _classify_item(text: str) -> Tuple[str, str, float]:
    t = _normalise_text(text).lower()

    if "notebook" in t:
        return "notebook", CATEGORY_PRICING["notebook"]["description"], 0.88
    if re.search(r"\bpens?\b", t):
        return "pen", CATEGORY_PRICING["pen"]["description"], 0.88
    if "t-shirt" in t or "tshirt" in t or "t shirt" in t:
        return "tshirt", CATEGORY_PRICING["tshirt"]["description"], 0.82
    if "shirt" in t or "fabric" in t or "xxxl" in t or "xxl" in t or "xl=" in t or "clothing" in t:
        return "clothing", CATEGORY_PRICING["clothing"]["description"], 0.78
    if "gift pack" in t or "corporate gift" in t:
        return "gift_pack", CATEGORY_PRICING["gift_pack"]["description"], 0.75

    # V43.1 strict rule:
    # Generic items are only allowed where there is a real supply hint.
    # This blocks background sentences like "4477 on 24 November 2000..."
    if _has_real_item_hint(t):
        return "generic", CATEGORY_PRICING["generic"]["description"], 0.55

    return "unknown", "", 0.0


def _extract_quantity(raw: Dict[str, Any]) -> Optional[float]:
    """
    V43.1 strict quantity extraction.

    Do NOT trust V42's raw numeric quantity blindly because V42 may extract
    date/reference numbers such as 4477 or telephone fragments as quantities.

    Only accept quantities when they are clearly attached to:
    - Quantity:
    - Qty:
    - 40 each / 40 units / 40 packs etc.
    """
    text = _normalise_text(raw.get("raw_text") or raw.get("description")).lower()

    patterns = [
        r"\bquantity\s*[:\-]?\s*(\d+(?:\.\d+)?)\b",
        r"\bqty\s*[:\-]?\s*(\d+(?:\.\d+)?)\b",
        r"\b(\d+(?:\.\d+)?)\s*(each|ea|units?|packs?|boxes|sets?|items?)\b",
    ]

    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            val = _safe_float(m.group(1))
            if val and 0 < val <= MAX_ACCEPTED_QUANTITY:
                return val

    return None


def _clean_description(raw: Dict[str, Any]) -> str:
    text = _normalise_text(raw.get("raw_text") or raw.get("description"))
    text = text.replace("▪", " ").replace("•", " ").replace("|", " ")
    text = re.sub(r"\bquantity\s*[:\-]?\s*\d+(?:\.\d+)?\b", " ", text, flags=re.I)
    text = re.sub(r"\bqty\s*[:\-]?\s*\d+(?:\.\d+)?\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -:;,.")
    return text


def _merge_duplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}

    for item in items:
        category = item["category"]
        existing = best.get(category)

        if existing is None:
            best[category] = item
            continue

        # Keep the richer description, but do not double count repeated same quantity rows.
        if len(item["clean_description"]) > len(existing["clean_description"]):
            existing["clean_description"] = item["clean_description"]
            existing["source_page"] = item.get("source_page") or existing.get("source_page")

        existing["confidence"] = max(existing["confidence"], item["confidence"])

        # Prefer explicit quantity, but never inflate by duplicate repeats.
        existing["quantity"] = max(existing["quantity"], item["quantity"])

    return list(best.values())


def _clean_v42_items(v42_payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    candidates: List[Dict[str, Any]] = []
    candidates.extend(v42_payload.get("line_items") or [])

    for raw in v42_payload.get("raw_candidates") or []:
        candidates.append({
            "description": raw.get("text"),
            "raw_text": raw.get("text"),
            "quantity": None,
            "page": raw.get("page"),
            "confidence": 0.35,
        })

    seen = set()
    for raw in candidates:
        desc = _clean_description(raw)
        key = desc.lower()[:160]
        if not desc or key in seen:
            continue
        seen.add(key)

        if _looks_false_positive(desc):
            rejected.append({
                "description": desc,
                "page": raw.get("page"),
                "reason": "false-positive policy/evaluation/contact/background/date/reference text",
            })
            continue

        category, final_desc, class_conf = _classify_item(desc)
        qty = _extract_quantity(raw)

        if qty and qty > MAX_ACCEPTED_QUANTITY:
            rejected.append({
                "description": desc,
                "page": raw.get("page"),
                "reason": "quantity too large — likely false positive",
            })
            continue

        if category == "unknown" or not qty:
            rejected.append({
                "description": desc,
                "page": raw.get("page"),
                "reason": "not a clear supply item or strict quantity missing",
            })
            continue

        accepted.append({
            "category": category,
            "description": final_desc,
            "clean_description": desc,
            "quantity": qty,
            "source_page": raw.get("page"),
            "confidence": round(max(float(raw.get("confidence") or 0.0), class_conf), 3),
            "reason": f"classified as {category}; strict quantity detected",
        })

    return _merge_duplicate_items(accepted), rejected


def _price_items(
    clean_items: List[Dict[str, Any]],
    margin_percent: float = DEFAULT_MARGIN_PERCENT,
    vat_rate_percent: float = DEFAULT_VAT_RATE,
) -> List[AutoPricedLineItem]:
    priced: List[AutoPricedLineItem] = []

    for idx, item in enumerate(clean_items, start=1):
        category = item["category"]
        rule = CATEGORY_PRICING.get(category, CATEGORY_PRICING["generic"])
        unit_cost = float(rule["unit_cost"])
        unit = rule["unit"]
        qty = float(item["quantity"])

        unit_price_excl = unit_cost / (1 - (margin_percent / 100.0))
        total_excl = unit_price_excl * qty
        vat = total_excl * (vat_rate_percent / 100.0)
        total_incl = total_excl + vat

        priced.append(
            AutoPricedLineItem(
                item_no=idx,
                description=item["description"],
                original_description=item["clean_description"],
                quantity=qty,
                unit=unit,
                estimated_unit_cost_excl_vat=_money(unit_cost),
                margin_percent=_money(margin_percent),
                unit_price_excl_vat=_money(unit_price_excl),
                total_excl_vat=_money(total_excl),
                vat_rate_percent=_money(vat_rate_percent),
                vat_amount=_money(vat),
                total_incl_vat=_money(total_incl),
                currency="ZAR",
                pricing_method="default_market_estimate_plus_margin",
                confidence=float(item["confidence"]),
                source_page=item.get("source_page"),
                reason=item["reason"],
            )
        )

    return priced


def _apply_profit_floor(
    items: List[AutoPricedLineItem],
    minimum_profit_required: float = DEFAULT_PROFIT_FLOOR,
) -> Tuple[List[AutoPricedLineItem], Dict[str, Any]]:
    current_profit = sum((i.unit_price_excl_vat - i.estimated_unit_cost_excl_vat) * i.quantity for i in items)

    if not items or current_profit >= minimum_profit_required:
        return items, {
            "applied": False,
            "minimum_profit_required": _money(minimum_profit_required),
            "current_profit_before_adjustment": _money(current_profit),
            "additional_profit_required": 0.0,
        }

    shortfall = minimum_profit_required - current_profit
    total_qty = sum(i.quantity for i in items) or 1
    add_per_unit = shortfall / total_qty

    adjusted: List[AutoPricedLineItem] = []
    for i in items:
        new_unit_excl = i.unit_price_excl_vat + add_per_unit
        new_total_excl = new_unit_excl * i.quantity
        new_vat = new_total_excl * (i.vat_rate_percent / 100.0)
        new_total_incl = new_total_excl + new_vat
        margin = ((new_unit_excl - i.estimated_unit_cost_excl_vat) / new_unit_excl) * 100 if new_unit_excl else i.margin_percent

        adjusted.append(
            AutoPricedLineItem(
                **{
                    **asdict(i),
                    "unit_price_excl_vat": _money(new_unit_excl),
                    "total_excl_vat": _money(new_total_excl),
                    "vat_amount": _money(new_vat),
                    "total_incl_vat": _money(new_total_incl),
                    "margin_percent": _money(margin),
                    "pricing_method": "profit_floor_adjusted_default_market_estimate",
                    "reason": i.reason + "; adjusted to meet profit floor",
                }
            )
        )

    return adjusted, {
        "applied": True,
        "minimum_profit_required": _money(minimum_profit_required),
        "current_profit_before_adjustment": _money(current_profit),
        "additional_profit_required": _money(shortfall),
        "distributed_evenly_per_unit_excl_vat": _money(add_per_unit),
    }


def build_auto_pricing_from_v42_payload(
    v42_payload: Dict[str, Any],
    buyer_rfq_number: Optional[str] = None,
    margin_percent: float = DEFAULT_MARGIN_PERCENT,
    minimum_profit_required: float = DEFAULT_PROFIT_FLOOR,
    vat_rate_percent: float = DEFAULT_VAT_RATE,
    apply_profit_floor: bool = True,
) -> Dict[str, Any]:
    started_at = _now_iso()
    clean_items, rejected_items = _clean_v42_items(v42_payload)

    priced_items = _price_items(
        clean_items,
        margin_percent=margin_percent,
        vat_rate_percent=vat_rate_percent,
    )

    profit_floor_adjustment = {
        "applied": False,
        "minimum_profit_required": _money(minimum_profit_required),
    }
    if apply_profit_floor:
        priced_items, profit_floor_adjustment = _apply_profit_floor(
            priced_items,
            minimum_profit_required=minimum_profit_required,
        )

    total_cost = _money(sum(i.estimated_unit_cost_excl_vat * i.quantity for i in priced_items))
    total_sell_excl = _money(sum(i.total_excl_vat for i in priced_items))
    total_vat = _money(sum(i.vat_amount for i in priced_items))
    total_sell_incl = _money(sum(i.total_incl_vat for i in priced_items))
    total_profit = _money(total_sell_excl - total_cost)
    achieved_margin = _money((total_profit / total_sell_excl) * 100) if total_sell_excl else 0.0

    status = "ok" if priced_items else "needs_manual_review"

    return {
        "status": status,
        "service_version": SERVICE_VERSION,
        "message": "Auto pricing completed." if priced_items else "No reliable supply items found for auto pricing.",
        "buyer_rfq_number": buyer_rfq_number or v42_payload.get("buyer_rfq_number"),
        "input_pdf": v42_payload.get("input_pdf"),
        "started_at": started_at,
        "completed_at": _now_iso(),
        "pricing_summary": {
            "currency": "ZAR",
            "vat_rate_percent": _money(vat_rate_percent),
            "minimum_margin_percent": _money(margin_percent),
            "minimum_profit_required": _money(minimum_profit_required),
            "line_items_count": len(priced_items),
            "total_cost_excl_vat": total_cost,
            "total_sell_excl_vat": total_sell_excl,
            "total_vat": total_vat,
            "total_sell_incl_vat": total_sell_incl,
            "total_profit": total_profit,
            "achieved_margin_percent": achieved_margin,
            "profit_floor_adjustment": profit_floor_adjustment,
        },
        "line_items": [asdict(i) for i in priced_items],
        "clean_items": clean_items,
        "rejected_items": rejected_items[:100],
        "source_v42_summary": v42_payload.get("summary", {}),
        "quote_engine_payload": {
            "buyer_rfq_number": buyer_rfq_number or v42_payload.get("buyer_rfq_number"),
            "input_pdf": v42_payload.get("input_pdf"),
            "currency": "ZAR",
            "vat_rate": vat_rate_percent,
            "line_items": [
                {
                    "description": i.description,
                    "quantity": i.quantity,
                    "unit": i.unit,
                    "unit_price": i.unit_price_excl_vat,
                    "line_total": i.total_excl_vat,
                    "vat_amount": i.vat_amount,
                    "line_total_incl_vat": i.total_incl_vat,
                }
                for i in priced_items
            ],
        },
    }


def auto_price_from_v42_json(
    v42_json_path: str,
    buyer_rfq_number: Optional[str] = None,
    output_dir: Optional[str] = None,
    margin_percent: float = DEFAULT_MARGIN_PERCENT,
    minimum_profit_required: float = DEFAULT_PROFIT_FLOOR,
    vat_rate_percent: float = DEFAULT_VAT_RATE,
    apply_profit_floor: bool = True,
) -> Dict[str, Any]:
    started_at = _now_iso()
    path = Path(v42_json_path)
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V42 JSON file not found.",
            "v42_json_path": str(path),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }

    try:
        v42_payload = json.loads(path.read_text(encoding="utf-8"))
        result = build_auto_pricing_from_v42_payload(
            v42_payload=v42_payload,
            buyer_rfq_number=buyer_rfq_number,
            margin_percent=margin_percent,
            minimum_profit_required=minimum_profit_required,
            vat_rate_percent=vat_rate_percent,
            apply_profit_floor=apply_profit_floor,
        )
        result["v42_json_path"] = str(path)
        return _write_result(result, output_dir)
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Auto pricing from V42 JSON failed.",
            "v42_json_path": str(path),
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def auto_price_pdf_with_v42(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    max_pages_scan: int = 25,
    output_dir: Optional[str] = None,
    margin_percent: float = DEFAULT_MARGIN_PERCENT,
    minimum_profit_required: float = DEFAULT_PROFIT_FLOOR,
    vat_rate_percent: float = DEFAULT_VAT_RATE,
    apply_profit_floor: bool = True,
    min_confidence: float = 0.35,
) -> Dict[str, Any]:
    started_at = _now_iso()
    try:
        from app.services.pricing_table_extraction_v42_service import analyse_pdf_with_v41_then_v42

        v42_payload = analyse_pdf_with_v41_then_v42(
            input_pdf=input_pdf,
            buyer_rfq_number=buyer_rfq_number,
            max_pages_scan=max_pages_scan,
            output_dir=None,
            min_confidence=min_confidence,
        )

        if v42_payload.get("status") != "ok":
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V42 failed, so V43 could not continue.",
                "v42_result": v42_payload,
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        result = build_auto_pricing_from_v42_payload(
            v42_payload=v42_payload,
            buyer_rfq_number=buyer_rfq_number,
            margin_percent=margin_percent,
            minimum_profit_required=minimum_profit_required,
            vat_rate_percent=vat_rate_percent,
            apply_profit_floor=apply_profit_floor,
        )
        result["v42_output_json"] = v42_payload.get("output_json")
        result["v41_result_summary"] = v42_payload.get("v41_result_summary")
        return _write_result(result, output_dir)

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V43 PDF auto pricing workflow failed.",
            "input_pdf": input_pdf,
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def _write_result(result: Dict[str, Any], output_dir: Optional[str]) -> Dict[str, Any]:
    out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not out_root.is_absolute():
        out_root = Path.cwd() / out_root
    out_root.mkdir(parents=True, exist_ok=True)

    safe_rfq = re.sub(r"[^A-Za-z0-9_.-]+", "-", result.get("buyer_rfq_number") or "RFQ").strip("-") or "RFQ"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_path = out_root / f"{safe_rfq}__{SERVICE_VERSION}__{timestamp}.json"

    result["output_json"] = str(out_path)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def get_auto_pricing_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V43.1 Auto Pricing Engine",
        "description": "Cleans V42 false positives, uses strict quantity detection, keeps real supply items, applies margin/profit-floor pricing, and outputs quote-engine-ready line_items.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "defaults": {
            "margin_percent": DEFAULT_MARGIN_PERCENT,
            "minimum_profit_required": DEFAULT_PROFIT_FLOOR,
            "vat_rate_percent": DEFAULT_VAT_RATE,
            "max_accepted_quantity": MAX_ACCEPTED_QUANTITY,
        },
        "endpoints": {
            "status": "/v43-auto-pricing/status",
            "auto_price_pdf": "/v43-auto-pricing/auto-price-pdf",
            "auto_price_v42_json": "/v43-auto-pricing/auto-price-v42-json",
        },
        "ready": True,
    }
