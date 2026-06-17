from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VAT_RATE = Decimal("0.15")
DEFAULT_MIN_MARGIN = Decimal("0.25")
DEFAULT_MIN_TOTAL_PROFIT = Decimal("30000.00")

EXCLUDED_KEYWORDS = {
    "medical",
    "medical consumables",
    "medical equipment",
    "pharmaceutical",
    "pharmaceuticals",
    "clinic",
    "hospital",
    "surgical",
    "syringe",
    "bandage",
    "it equipment",
    "information technology",
    "laptop",
    "laptops",
    "computer",
    "computers",
    "printer",
    "printers",
    "server",
    "servers",
    "router",
    "software",
    "software license",
    "tablet",
    "fuel",
    "petrol",
    "diesel",
    "catering",
    "food",
    "refreshments",
}

SUPPLY_HINTS = {
    "supply",
    "delivery",
    "deliver",
    "supply and delivery",
    "supply, deliver and offload",
    "goods",
    "materials",
    "furniture",
    "office furniture",
    "office chairs",
    "stationery",
    "cleaning materials",
    "uniform",
    "ppe",
    "consumables",
}

UOM_ALIASES = {
    "ea": "Each",
    "each": "Each",
    "unit": "Each",
    "item": "Each",
    "pcs": "Each",
    "piece": "Each",
    "pieces": "Each",
    "box": "Box",
    "boxes": "Box",
    "ream": "Ream",
    "reams": "Ream",
    "set": "Set",
    "sets": "Set",
    "pack": "Pack",
    "packs": "Pack",
    "litre": "Litre",
    "litres": "Litre",
    "liter": "Litre",
    "liters": "Litre",
    "kg": "Kg",
    "kilogram": "Kg",
    "kilograms": "Kg",
    "m": "Meter",
    "meter": "Meter",
    "metre": "Meter",
}

FALLBACK_COST_RULES = [
    (("ergonomic office chair",), Decimal("1450.00")),
    (("office chair", "chair"), Decimal("1200.00")),
    (("executive chair",), Decimal("1850.00")),
    (("visitor chair",), Decimal("950.00")),
    (("desk",), Decimal("2800.00")),
    (("table",), Decimal("2200.00")),
    (("cabinet",), Decimal("3100.00")),
    (("filing cabinet",), Decimal("3400.00")),
    (("bookshelf", "book shelf"), Decimal("2600.00")),
    (("office furniture", "furniture"), Decimal("2500.00")),
    (("paper", "a4 paper", "ream"), Decimal("90.00")),
    (("toner",), Decimal("850.00")),
    (("ink cartridge", "cartridge"), Decimal("650.00")),
    (("stationery",), Decimal("120.00")),
    (("pen",), Decimal("8.00")),
    (("pencil",), Decimal("6.00")),
    (("file", "lever arch"), Decimal("35.00")),
    (("cleaning material", "cleaning materials", "detergent"), Decimal("180.00")),
    (("gloves",), Decimal("95.00")),
    (("uniform",), Decimal("450.00")),
    (("overall",), Decimal("390.00")),
    (("ppe", "protective clothing"), Decimal("520.00")),
    (("boots", "safety boots"), Decimal("650.00")),
    (("water", "bottled water"), Decimal("75.00")),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _to_decimal(value: Any, default: str = "0.00") -> Decimal:
    try:
        if value is None or value == "":
            return Decimal(default)
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        cleaned = (
            str(value)
            .replace("R", "")
            .replace("ZAR", "")
            .replace("zar", "")
            .replace(",", "")
            .strip()
        )
        return Decimal(cleaned)
    except Exception:
        return Decimal(default)


def _money(value: Any) -> Decimal:
    return _to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _contains_any(text: str, keywords: set[str]) -> bool:
    blob = _safe_lower(text)
    return any(word in blob for word in keywords)


@dataclass
class PricingLineResult:
    line_no: int
    description: str
    quantity: Decimal
    unit_of_measure: str
    supplier_unit_cost: Decimal
    landed_unit_cost: Decimal
    markup_percent: Decimal
    margin_percent: Decimal
    selling_unit_price_excl_vat: Decimal
    line_total_excl_vat: Decimal
    vat_amount: Decimal
    line_total_incl_vat: Decimal
    line_profit: Decimal
    source: str
    quote_reference: str = ""
    schedule_item_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        for key, value in payload.items():
            if isinstance(value, Decimal):
                payload[key] = float(value)
        return payload


class PricingEngine:
    @classmethod
    def evaluate_rfq_eligibility(cls, rfq_payload: Dict[str, Any]) -> Dict[str, Any]:
        title = _normalize_spaces(_safe_str(rfq_payload.get("title")))
        description = _normalize_spaces(_safe_str(rfq_payload.get("description")))
        combined = f"{title} {description}".strip().lower()

        excluded_hits = [kw for kw in sorted(EXCLUDED_KEYWORDS) if kw in combined]
        supply_hits = [kw for kw in sorted(SUPPLY_HINTS) if kw in combined]

        briefing_required = bool(rfq_payload.get("briefing_required", False))
        eligible = True
        reasons: List[str] = []

        if excluded_hits:
            eligible = False
            reasons.append(f"Excluded category detected: {', '.join(excluded_hits)}")

        if briefing_required:
            eligible = False
            reasons.append("Compulsory briefing detected")

        if not supply_hits and not cls._looks_like_supply_from_items(rfq_payload.get("items") or rfq_payload.get("line_items") or []):
            eligible = False
            reasons.append("RFQ does not clearly appear to be a supply-and-delivery opportunity")

        return {
            "eligible": eligible,
            "reasons": reasons,
            "excluded_hits": excluded_hits,
            "supply_hits": supply_hits,
        }

    @classmethod
    def _looks_like_supply_from_items(cls, items: List[Dict[str, Any]]) -> bool:
        if not isinstance(items, list):
            return False
        for item in items:
            if not isinstance(item, dict):
                continue
            text = " ".join(
                [
                    _safe_str(item.get("description")),
                    _safe_str(item.get("item_description")),
                    _safe_str(item.get("name")),
                ]
            ).lower()
            if text and not _contains_any(text, EXCLUDED_KEYWORDS):
                return True
        return False

    @classmethod
    def _normalize_uom(cls, value: Any) -> str:
        raw = _safe_lower(value)
        if not raw:
            return "Each"
        return UOM_ALIASES.get(raw, _safe_str(value).title())

    @classmethod
    def _extract_items(cls, rfq_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_items = (
            rfq_payload.get("items")
            or rfq_payload.get("line_items")
            or rfq_payload.get("buyer_schedule")
            or rfq_payload.get("buyer_pricing_schedule")
            or []
        )

        extracted: List[Dict[str, Any]] = []

        if not isinstance(raw_items, list):
            raw_items = []

        for idx, raw in enumerate(raw_items, start=1):
            if not isinstance(raw, dict):
                continue

            description = (
                _safe_str(raw.get("description"))
                or _safe_str(raw.get("item_description"))
                or _safe_str(raw.get("name"))
                or f"Item {idx}"
            )

            quantity = _to_decimal(
                raw.get("quantity")
                or raw.get("qty")
                or raw.get("units")
                or 1,
                default="1",
            )
            if quantity <= 0:
                quantity = Decimal("1")

            uom = cls._normalize_uom(
                raw.get("unit_of_measure")
                or raw.get("uom")
                or raw.get("unit")
                or "Each"
            )

            item_code = _safe_str(raw.get("item_code") or raw.get("code"))
            supplier_unit_cost = _to_decimal(
                raw.get("supplier_unit_cost")
                or raw.get("estimated_unit_cost")
                or raw.get("cost_price"),
                default="0.00",
            )

            extracted.append(
                {
                    "description": description,
                    "quantity": quantity,
                    "unit_of_measure": uom,
                    "item_code": item_code,
                    "supplier_unit_cost": supplier_unit_cost,
                    "raw": raw,
                }
            )

        if not extracted:
            extracted.append(
                {
                    "description": _safe_str(
                        rfq_payload.get("title")
                        or rfq_payload.get("description")
                        or "Supply and delivery item"
                    ),
                    "quantity": Decimal("1"),
                    "unit_of_measure": "Each",
                    "item_code": "",
                    "supplier_unit_cost": Decimal("0.00"),
                    "raw": {},
                }
            )

        return extracted

    @classmethod
    def _match_key(cls, text: str) -> str:
        normalized = _safe_lower(text)
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @classmethod
    def _build_supplier_index(cls, supplier_quotes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        index: Dict[str, Dict[str, Any]] = {}

        for quote in supplier_quotes or []:
            if not isinstance(quote, dict):
                continue

            items = quote.get("items") or quote.get("line_items") or []
            quote_ref = _safe_str(
                quote.get("quote_number")
                or quote.get("quote_reference")
                or quote.get("reference")
                or quote.get("supplier_name")
            )
            supplier_name = _safe_str(quote.get("supplier_name"))

            for item in items:
                if not isinstance(item, dict):
                    continue

                description = (
                    _safe_str(item.get("description"))
                    or _safe_str(item.get("item_description"))
                    or _safe_str(item.get("name"))
                )
                if not description:
                    continue

                unit_cost = _to_decimal(
                    item.get("unit_price")
                    or item.get("unit_cost")
                    or item.get("price")
                    or item.get("rate"),
                    default="0.00",
                )

                if unit_cost <= 0:
                    continue

                key = cls._match_key(description)
                current = index.get(key)

                candidate = {
                    "description": description,
                    "unit_cost": unit_cost,
                    "supplier_name": supplier_name,
                    "quote_reference": quote_ref,
                    "source": "supplier_quote",
                }

                if current is None or unit_cost < current["unit_cost"]:
                    index[key] = candidate

        return index

    @classmethod
    def _lookup_supplier_price(cls, description: str, supplier_index: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        exact_key = cls._match_key(description)
        if exact_key in supplier_index:
            return supplier_index[exact_key]

        desc_words = set(exact_key.split())
        best_score = 0
        best_match: Optional[Dict[str, Any]] = None

        for key, item in supplier_index.items():
            overlap = len(desc_words & set(key.split()))
            if overlap > best_score:
                best_score = overlap
                best_match = item

        if best_score >= 2:
            return best_match
        return None

    @classmethod
    def _estimate_fallback_unit_cost(cls, item: Dict[str, Any]) -> Decimal:
        explicit = _to_decimal(item.get("supplier_unit_cost"), default="0.00")
        if explicit > 0:
            return _round_money(explicit)

        desc = _safe_lower(item.get("description"))

        for aliases, base_cost in FALLBACK_COST_RULES:
            if any(alias in desc for alias in aliases):
                heuristic = base_cost
                break
        else:
            heuristic = Decimal("350.00")

        quantity = _to_decimal(item.get("quantity"), default="1")

        if quantity >= 500:
            heuristic *= Decimal("0.88")
        elif quantity >= 100:
            heuristic *= Decimal("0.93")
        elif quantity >= 50:
            heuristic *= Decimal("0.97")

        return _round_money(heuristic)

    @classmethod
    def _price_line_item(
        cls,
        line_no: int,
        item: Dict[str, Any],
        supplier_index: Dict[str, Dict[str, Any]],
        min_margin: Decimal,
        include_vat: bool,
        transport_rate: Decimal,
        contingency_rate: Decimal,
        labour_rate: Decimal,
    ) -> PricingLineResult:
        description = _safe_str(item.get("description"))
        quantity = _to_decimal(item.get("quantity"), default="1")
        if quantity <= 0:
            quantity = Decimal("1")

        uom = cls._normalize_uom(item.get("unit_of_measure") or "Each")
        item_code = _safe_str(item.get("item_code"))

        matched_supplier = cls._lookup_supplier_price(description, supplier_index)
        if matched_supplier:
            supplier_unit_cost = _round_money(_to_decimal(matched_supplier["unit_cost"]))
            source = matched_supplier.get("source", "supplier_quote")
            quote_reference = _safe_str(matched_supplier.get("quote_reference"))
        else:
            supplier_unit_cost = cls._estimate_fallback_unit_cost(item)
            source = "fallback_estimate"
            quote_reference = ""

        landed_unit_cost = supplier_unit_cost * (Decimal("1.00") + transport_rate + contingency_rate + labour_rate)
        landed_unit_cost = _round_money(landed_unit_cost)

        selling_unit_price_excl_vat = landed_unit_cost / (Decimal("1.00") - min_margin)
        selling_unit_price_excl_vat = _round_money(selling_unit_price_excl_vat)

        line_total_excl_vat = _round_money(selling_unit_price_excl_vat * quantity)
        vat_amount = _round_money(line_total_excl_vat * VAT_RATE) if include_vat else Decimal("0.00")
        line_total_incl_vat = _round_money(line_total_excl_vat + vat_amount)

        line_cost_total = _round_money(landed_unit_cost * quantity)
        line_profit = _round_money(line_total_excl_vat - line_cost_total)

        margin_percent = Decimal("0.00")
        if line_total_excl_vat > 0:
            margin_percent = _round_money((line_profit / line_total_excl_vat) * Decimal("100"))

        markup_percent = Decimal("0.00")
        if landed_unit_cost > 0:
            markup_percent = _round_money(
                ((selling_unit_price_excl_vat - landed_unit_cost) / landed_unit_cost) * Decimal("100")
            )

        return PricingLineResult(
            line_no=line_no,
            description=description,
            quantity=_round_money(quantity),
            unit_of_measure=uom,
            supplier_unit_cost=supplier_unit_cost,
            landed_unit_cost=landed_unit_cost,
            markup_percent=markup_percent,
            margin_percent=margin_percent,
            selling_unit_price_excl_vat=selling_unit_price_excl_vat,
            line_total_excl_vat=line_total_excl_vat,
            vat_amount=vat_amount,
            line_total_incl_vat=line_total_incl_vat,
            line_profit=line_profit,
            source=source,
            quote_reference=quote_reference,
            schedule_item_code=item_code,
        )

    @classmethod
    def _apply_profit_floor(
        cls,
        line_results: List[PricingLineResult],
        current_total_profit: Decimal,
        required_total_profit: Decimal,
        include_vat: bool,
    ) -> Dict[str, Any]:
        if not line_results or current_total_profit >= required_total_profit:
            return {
                "applied": False,
                "added_profit": 0.0,
                "reason": "Not required",
            }

        shortfall = required_total_profit - current_total_profit
        total_quantity = sum((line.quantity for line in line_results), Decimal("0.00"))
        if total_quantity <= 0:
            total_quantity = Decimal(str(len(line_results)))

        extra_per_unit = _round_money(shortfall / total_quantity)

        for line in line_results:
            line.selling_unit_price_excl_vat = _round_money(line.selling_unit_price_excl_vat + extra_per_unit)
            line.line_total_excl_vat = _round_money(line.selling_unit_price_excl_vat * line.quantity)
            line.vat_amount = _round_money(line.line_total_excl_vat * VAT_RATE) if include_vat else Decimal("0.00")
            line.line_total_incl_vat = _round_money(line.line_total_excl_vat + line.vat_amount)

            line_cost_total = _round_money(line.landed_unit_cost * line.quantity)
            line.line_profit = _round_money(line.line_total_excl_vat - line_cost_total)

            if line.line_total_excl_vat > 0:
                line.margin_percent = _round_money((line.line_profit / line.line_total_excl_vat) * Decimal("100"))
            if line.landed_unit_cost > 0:
                line.markup_percent = _round_money(
                    ((line.selling_unit_price_excl_vat - line.landed_unit_cost) / line.landed_unit_cost)
                    * Decimal("100")
                )

        return {
            "applied": True,
            "added_profit": float(_round_money(shortfall)),
            "method": "distributed_evenly_across_all_units",
        }

    @classmethod
    def _build_buyer_schedule(cls, line_results: List[PricingLineResult]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []

        for line in line_results:
            rows.append(
                {
                    "row_no": line.line_no,
                    "item_code": line.schedule_item_code,
                    "description": line.description,
                    "quantity": float(line.quantity),
                    "unit": line.unit_of_measure,
                    "rate_excl_vat": float(line.selling_unit_price_excl_vat),
                    "amount_excl_vat": float(line.line_total_excl_vat),
                    "vat_amount": float(line.vat_amount),
                    "amount_incl_vat": float(line.line_total_incl_vat),
                    "source": line.source,
                    "quote_reference": line.quote_reference,
                }
            )

        return rows

    @classmethod
    def price_rfq(
        cls,
        rfq_payload: Dict[str, Any],
        supplier_quotes: Optional[List[Dict[str, Any]]] = None,
        pricing_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pricing_context = pricing_context or {}
        supplier_quotes = supplier_quotes or []

        eligibility = cls.evaluate_rfq_eligibility(rfq_payload)

        min_margin = _to_decimal(
            pricing_context.get("min_margin")
            or rfq_payload.get("min_margin")
            or os.getenv("LMCP_DEFAULT_MIN_MARGIN", str(DEFAULT_MIN_MARGIN)),
            default="0.25",
        )
        min_profit_total = _to_decimal(
            pricing_context.get("min_profit_total")
            or rfq_payload.get("min_profit_total")
            or os.getenv("LMCP_MIN_TOTAL_PROFIT", str(DEFAULT_MIN_TOTAL_PROFIT)),
            default="30000.00",
        )
        include_vat = bool(pricing_context.get("include_vat", rfq_payload.get("include_vat", True)))

        transport_rate = _to_decimal(
            pricing_context.get("transport_rate")
            or rfq_payload.get("transport_rate")
            or os.getenv("LMCP_TRANSPORT_RATE", "0.03"),
            default="0.03",
        )
        contingency_rate = _to_decimal(
            pricing_context.get("contingency_rate")
            or rfq_payload.get("contingency_rate")
            or os.getenv("LMCP_CONTINGENCY_RATE", "0.02"),
            default="0.02",
        )
        labour_rate = _to_decimal(
            pricing_context.get("labour_rate")
            or rfq_payload.get("labour_rate")
            or os.getenv("LMCP_LIGHT_HANDLING_RATE", "0.00"),
            default="0.00",
        )

        items = cls._extract_items(rfq_payload)
        supplier_index = cls._build_supplier_index(supplier_quotes)

        line_results: List[PricingLineResult] = []
        total_cost = Decimal("0.00")
        total_sell_excl = Decimal("0.00")
        total_vat = Decimal("0.00")
        total_profit = Decimal("0.00")

        for idx, item in enumerate(items, start=1):
            line = cls._price_line_item(
                line_no=idx,
                item=item,
                supplier_index=supplier_index,
                min_margin=min_margin,
                include_vat=include_vat,
                transport_rate=transport_rate,
                contingency_rate=contingency_rate,
                labour_rate=labour_rate,
            )
            line_results.append(line)
            total_cost += _round_money(line.landed_unit_cost * line.quantity)
            total_sell_excl += line.line_total_excl_vat
            total_vat += line.vat_amount
            total_profit += line.line_profit

        adjustment = None
        if line_results and total_profit < min_profit_total:
            adjustment = cls._apply_profit_floor(
                line_results=line_results,
                current_total_profit=total_profit,
                required_total_profit=min_profit_total,
                include_vat=include_vat,
            )
            total_cost = sum((_round_money(line.landed_unit_cost * line.quantity) for line in line_results), Decimal("0.00"))
            total_sell_excl = sum((line.line_total_excl_vat for line in line_results), Decimal("0.00"))
            total_vat = sum((line.vat_amount for line in line_results), Decimal("0.00"))
            total_profit = sum((line.line_profit for line in line_results), Decimal("0.00"))

        total_incl = total_sell_excl + total_vat
        achieved_margin = Decimal("0.00")
        if total_sell_excl > 0:
            achieved_margin = _round_money((total_profit / total_sell_excl) * Decimal("100"))

        quote_ready = bool(eligibility["eligible"] and line_results)

        return {
            "status": "ok" if line_results else "failed",
            "priced_at": _utc_now_iso(),
            "eligible": eligibility["eligible"],
            "eligibility_reasons": eligibility["reasons"],
            "quote_ready": quote_ready,
            "pricing_summary": {
                "currency": "ZAR",
                "line_count": len(line_results),
                "total_cost_excl_vat": float(_round_money(total_cost)),
                "total_sell_excl_vat": float(_round_money(total_sell_excl)),
                "total_vat": float(_round_money(total_vat)),
                "total_sell_incl_vat": float(_round_money(total_incl)),
                "total_profit": float(_round_money(total_profit)),
                "achieved_margin_percent": float(_round_money(achieved_margin)),
                "minimum_margin_percent": float(_round_money(min_margin * Decimal("100"))),
                "minimum_profit_required": float(_round_money(min_profit_total)),
                "profit_floor_adjustment": adjustment,
                "vat_included": include_vat,
            },
            "pricing_inputs": {
                "min_margin": float(min_margin),
                "min_profit_total": float(min_profit_total),
                "transport_rate": float(transport_rate),
                "contingency_rate": float(contingency_rate),
                "labour_rate": float(labour_rate),
                "supplier_quotes_count": len(supplier_quotes),
            },
            "buyer_schedule": cls._build_buyer_schedule(line_results),
            "line_items": [line.to_dict() for line in line_results],
        }

    @classmethod
    def save_pricing_output(
        cls,
        pricing_result: Dict[str, Any],
        output_dir: str,
        buyer_rfq_number: str,
        quote_number: str,
    ) -> Dict[str, Any]:
        os.makedirs(output_dir, exist_ok=True)

        safe_rfq = re.sub(r"[^A-Za-z0-9._-]+", "-", _safe_str(buyer_rfq_number, "rfq-missing")).strip("-") or "rfq-missing"
        safe_quote = re.sub(r"[^A-Za-z0-9._-]+", "-", _safe_str(quote_number, "quote-missing")).strip("-") or "quote-missing"

        pricing_json_path = os.path.join(output_dir, f"{safe_rfq}__{safe_quote}__pricing.json")
        schedule_json_path = os.path.join(output_dir, f"{safe_rfq}__{safe_quote}__buyer_schedule.json")

        with open(pricing_json_path, "w", encoding="utf-8") as handle:
            json.dump(pricing_result, handle, indent=2, ensure_ascii=False)

        with open(schedule_json_path, "w", encoding="utf-8") as handle:
            json.dump(pricing_result.get("buyer_schedule") or [], handle, indent=2, ensure_ascii=False)

        return {
            "pricing_json_path": pricing_json_path,
            "buyer_schedule_json_path": schedule_json_path,
        }


def price_rfq_payload(
    rfq_payload: Dict[str, Any],
    supplier_quotes: Optional[List[Dict[str, Any]]] = None,
    pricing_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return PricingEngine.price_rfq(
        rfq_payload=rfq_payload,
        supplier_quotes=supplier_quotes,
        pricing_context=pricing_context,
    )


# =============================================================================
# COMPATIBILITY WRAPPER: revenue_dashboard_api expects build_supply_quote
# =============================================================================

from typing import Any, Dict, List


def build_supply_quote(
    items: List[Dict[str, Any]],
    markup_percent: float = 25.0,
    vat_rate: float = 0.15,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Compatibility wrapper for older modules that import build_supply_quote
    from pricing_engine.py.

    This function builds a supply quote summary from a list of items.
    Each item may contain:
      - description
      - quantity
      - unit_price
      - cost_price
      - unit_cost

    Pricing logic:
      - if unit_price exists, it is used directly
      - otherwise cost_price / unit_cost is marked up by markup_percent
      - VAT is added at vat_rate
    """

    def _clean_number(value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except Exception:
            return default

    normalized_items: List[Dict[str, Any]] = []
    subtotal = 0.0

    for raw in items or []:
        if not isinstance(raw, dict):
            continue

        description = str(raw.get("description") or raw.get("item_description") or raw.get("name") or "").strip()
        quantity = _clean_number(raw.get("quantity"), 0.0)

        direct_unit_price = raw.get("unit_price")
        cost_price = raw.get("cost_price", raw.get("unit_cost"))

        if direct_unit_price not in (None, ""):
            unit_price = _clean_number(direct_unit_price, 0.0)
        else:
            base_cost = _clean_number(cost_price, 0.0)
            unit_price = round(base_cost * (1 + (markup_percent / 100.0)), 2)

        line_total = round(quantity * unit_price, 2)
        subtotal += line_total

        normalized_items.append(
            {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    subtotal = round(subtotal, 2)
    vat_amount = round(subtotal * vat_rate, 2)
    total = round(subtotal + vat_amount, 2)

    return {
        "status": "ok",
        "items": normalized_items,
        "subtotal": subtotal,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total": total,
        "markup_percent": markup_percent,
    }
