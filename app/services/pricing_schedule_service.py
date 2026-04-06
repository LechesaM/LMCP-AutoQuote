from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional


TWOPLACES = Decimal("0.01")
DEFAULT_CURRENCY = "ZAR"
DEFAULT_MARKUP_PERCENT = Decimal("25.00")
DEFAULT_VAT_PERCENT = Decimal("15.00")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_decimal(value: Any, default: str = "0.00") -> Decimal:
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        text = str(value).replace(",", "").strip()
        if text == "":
            return Decimal(default)
        return Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _safe_float(value: Decimal) -> float:
    return float(_round_money(value))


@dataclass
class PricingScheduleItem:
    line_no: str
    description: str
    unit: str
    quantity: Decimal
    cost_rate: Decimal
    markup_percent: Decimal
    sell_rate: Decimal
    line_total: Decimal
    buyer_item_code: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["quantity"] = _safe_float(self.quantity)
        payload["cost_rate"] = _safe_float(self.cost_rate)
        payload["markup_percent"] = _safe_float(self.markup_percent)
        payload["sell_rate"] = _safe_float(self.sell_rate)
        payload["line_total"] = _safe_float(self.line_total)
        return payload


class PricingScheduleService:
    """
    Completes the buyer's requested pricing schedule from a normalized RFQ payload.

    Expected RFQ shape (flexible):
    {
        "title": "...",
        "buyer_name": "...",
        "currency": "ZAR",
        "vat_percent": 15,
        "markup_percent": 25,
        "line_items": [
            {
                "line_no": "1",
                "description": "Supply and deliver office chairs",
                "unit": "Each",
                "quantity": 20,
                "estimated_cost": 850.00
            }
        ]
    }

    Supported alternate keys for line items:
    - items
    - boq_items
    - pricing_schedule_items

    Supported alternate cost keys:
    - estimated_cost
    - cost_rate
    - unit_cost
    - base_cost

    Supported alternate quantity keys:
    - quantity
    - qty
    - number

    Supported alternate unit keys:
    - unit
    - uom
    """

    @classmethod
    def complete_buyer_pricing_schedule(
        cls,
        rfq: Dict[str, Any],
        default_markup_percent: float = 25.0,
        default_vat_percent: float = 15.0,
    ) -> Dict[str, Any]:
        currency = _safe_str(rfq.get("currency"), DEFAULT_CURRENCY) or DEFAULT_CURRENCY
        markup_percent = cls._resolve_markup_percent(rfq, default_markup_percent)
        vat_percent = cls._resolve_vat_percent(rfq, default_vat_percent)

        raw_items = cls._extract_line_items(rfq)
        completed_items: List[PricingScheduleItem] = []
        errors: List[str] = []

        for index, raw in enumerate(raw_items, start=1):
            try:
                item = cls._complete_line_item(
                    raw=raw,
                    fallback_line_no=str(index),
                    markup_percent=markup_percent,
                )
                completed_items.append(item)
            except Exception as exc:
                errors.append(f"Line {index}: {exc}")

        subtotal = _round_money(sum((item.line_total for item in completed_items), Decimal("0.00")))
        vat_amount = _round_money(subtotal * (vat_percent / Decimal("100.00")))
        grand_total = _round_money(subtotal + vat_amount)

        return {
            "status": "completed" if completed_items else "failed",
            "generated_at": _now_iso(),
            "schedule_name": cls._resolve_schedule_name(rfq),
            "quotation_title": _safe_str(rfq.get("title"), "Quotation"),
            "buyer_name": _safe_str(rfq.get("buyer_name") or rfq.get("client_name") or rfq.get("company_name")),
            "rfq_number": _safe_str(rfq.get("rfq_number") or rfq.get("reference_number") or rfq.get("tender_number")),
            "currency": currency,
            "vat_percent": _safe_float(vat_percent),
            "markup_percent": _safe_float(markup_percent),
            "items_count": len(completed_items),
            "items": [item.to_dict() for item in completed_items],
            "subtotal": _safe_float(subtotal),
            "vat_amount": _safe_float(vat_amount),
            "grand_total": _safe_float(grand_total),
            "errors": errors,
        }

    @classmethod
    def is_schedule_completeable(cls, rfq: Dict[str, Any]) -> bool:
        raw_items = cls._extract_line_items(rfq)
        if not raw_items:
            return False

        valid_count = 0
        for raw in raw_items:
            description = _safe_str(raw.get("description") or raw.get("item_description"))
            quantity = _to_decimal(raw.get("quantity", raw.get("qty", raw.get("number", "0"))))
            if description and quantity > 0:
                valid_count += 1

        return valid_count > 0

    @classmethod
    def _resolve_schedule_name(cls, rfq: Dict[str, Any]) -> str:
        return (
            _safe_str(rfq.get("schedule_name"))
            or _safe_str(rfq.get("pricing_schedule_name"))
            or "Buyer Pricing Schedule"
        )

    @classmethod
    def _resolve_markup_percent(cls, rfq: Dict[str, Any], default_markup_percent: float) -> Decimal:
        value = (
            rfq.get("markup_percent")
            or rfq.get("default_markup_percent")
            or default_markup_percent
        )
        result = _to_decimal(value, default=str(default_markup_percent))
        if result <= 0:
            result = DEFAULT_MARKUP_PERCENT
        return result

    @classmethod
    def _resolve_vat_percent(cls, rfq: Dict[str, Any], default_vat_percent: float) -> Decimal:
        value = rfq.get("vat_percent", default_vat_percent)
        result = _to_decimal(value, default=str(default_vat_percent))
        if result < 0:
            result = DEFAULT_VAT_PERCENT
        return result

    @classmethod
    def _extract_line_items(cls, rfq: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates = [
            rfq.get("line_items"),
            rfq.get("items"),
            rfq.get("boq_items"),
            rfq.get("pricing_schedule_items"),
        ]
        for candidate in candidates:
            if isinstance(candidate, list) and candidate:
                return [item for item in candidate if isinstance(item, dict)]
        return []

    @classmethod
    def _complete_line_item(
        cls,
        raw: Dict[str, Any],
        fallback_line_no: str,
        markup_percent: Decimal,
    ) -> PricingScheduleItem:
        line_no = _safe_str(
            raw.get("line_no")
            or raw.get("item_no")
            or raw.get("line_number")
            or fallback_line_no
        )

        description = _safe_str(raw.get("description") or raw.get("item_description"))
        if not description:
            raise ValueError("missing description")

        unit = _safe_str(raw.get("unit") or raw.get("uom") or "Item")

        quantity = _to_decimal(raw.get("quantity", raw.get("qty", raw.get("number", "0"))))
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        cost_rate = cls._resolve_cost_rate(raw)
        if cost_rate < 0:
            raise ValueError("cost_rate cannot be negative")

        item_markup = _to_decimal(raw.get("markup_percent"), default=str(markup_percent))
        if item_markup <= 0:
            item_markup = markup_percent

        sell_rate = _round_money(cost_rate * (Decimal("1.00") + (item_markup / Decimal("100.00"))))
        line_total = _round_money(sell_rate * quantity)

        return PricingScheduleItem(
            line_no=line_no,
            description=description,
            unit=unit,
            quantity=_round_money(quantity),
            cost_rate=_round_money(cost_rate),
            markup_percent=_round_money(item_markup),
            sell_rate=sell_rate,
            line_total=line_total,
            buyer_item_code=_safe_str(raw.get("buyer_item_code") or raw.get("item_code")) or None,
            notes=_safe_str(raw.get("notes")) or None,
        )

    @classmethod
    def _resolve_cost_rate(cls, raw: Dict[str, Any]) -> Decimal:
        for key in ["estimated_cost", "cost_rate", "unit_cost", "base_cost", "cost"]:
            if key in raw and raw.get(key) is not None:
                return _to_decimal(raw.get(key))
        return Decimal("0.00")
