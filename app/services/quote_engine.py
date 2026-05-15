from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional
from uuid import uuid4


TWOPLACES = Decimal("0.01")
DEFAULT_VAT_RATE = Decimal("0.15")
DEFAULT_VALIDITY_DAYS = 30
DEFAULT_DELIVERY_DAYS = 14
DEFAULT_MARGIN_RATE = Decimal("0.25")


def _to_decimal(value: Any, default: str = "0.00") -> Decimal:
    try:
        if value is None:
            return Decimal(default)
        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            return Decimal(default)
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _money(value: Any) -> Decimal:
    return _to_decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return default
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


def _extract_first_non_empty(source: Dict[str, Any], keys: List[str], default: str = "") -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _extract_first_number(source: Dict[str, Any], keys: List[str], default: Decimal = Decimal("0.00")) -> Decimal:
    for key in keys:
        if key in source and source.get(key) is not None and str(source.get(key)).strip() != "":
            value = _to_decimal(source.get(key), str(default))
            return value
    return default


def _normalise_line_items(rfq: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_items = (
        rfq.get("line_items")
        or rfq.get("items")
        or rfq.get("bill_of_quantities")
        or rfq.get("pricing_schedule")
        or rfq.get("quantities")
        or []
    )

    normalised: List[Dict[str, Any]] = []

    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    if not isinstance(raw_items, list):
        raw_items = []

    for idx, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            item = {"description": str(item)}

        description = _extract_first_non_empty(
            item,
            [
                "description",
                "item_description",
                "name",
                "title",
                "specification",
                "product_name",
            ],
            default=f"Line Item {idx}",
        )

        unit = _extract_first_non_empty(
            item,
            ["unit", "uom", "measure", "unit_of_measure"],
            default="Each",
        )

        quantity = _extract_first_number(
            item,
            ["quantity", "qty", "estimated_quantity", "number", "count"],
            default=Decimal("1"),
        )

        if quantity <= 0:
            quantity = Decimal("1")

        estimated_unit_price = _extract_first_number(
            item,
            [
                "unit_price",
                "estimated_unit_price",
                "budget_unit_price",
                "price",
                "rate",
                "estimated_rate",
            ],
            default=Decimal("0.00"),
        )

        estimated_line_total = _extract_first_number(
            item,
            [
                "line_total",
                "estimated_total",
                "total",
                "budget_total",
                "amount",
                "value",
            ],
            default=Decimal("0.00"),
        )

        normalised.append(
            {
                "line_number": idx,
                "description": description,
                "unit": unit,
                "quantity": quantity,
                "estimated_unit_price": estimated_unit_price,
                "estimated_line_total": estimated_line_total,
                "raw_item": deepcopy(item),
            }
        )

    if not normalised:
        fallback_description = _extract_first_non_empty(
            rfq,
            ["title", "description", "tender_description", "scope"],
            default="Supply and delivery item",
        )

        normalised.append(
            {
                "line_number": 1,
                "description": fallback_description,
                "unit": "Lot",
                "quantity": Decimal("1"),
                "estimated_unit_price": Decimal("0.00"),
                "estimated_line_total": Decimal("0.00"),
                "raw_item": {},
            }
        )

    return normalised


def _resolve_unit_price(
    item: Dict[str, Any],
    rfq_estimated_total: Decimal,
    fallback_margin_rate: Decimal,
    total_items_count: int,
) -> Decimal:
    quantity = _to_decimal(item.get("quantity"), "1")
    if quantity <= 0:
        quantity = Decimal("1")

    explicit_unit_price = _to_decimal(item.get("estimated_unit_price"), "0.00")
    explicit_line_total = _to_decimal(item.get("estimated_line_total"), "0.00")

    if explicit_unit_price > 0:
        base_cost = explicit_unit_price
    elif explicit_line_total > 0 and quantity > 0:
        base_cost = explicit_line_total / quantity
    elif rfq_estimated_total > 0 and total_items_count > 0:
        per_item_total = rfq_estimated_total / Decimal(str(total_items_count))
        base_cost = per_item_total / quantity
    else:
        base_cost = Decimal("0.00")

    sell_price = base_cost * (Decimal("1.00") + fallback_margin_rate)
    return sell_price.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass
class QuoteItem:
    line_number: int
    description: str
    unit: str
    quantity: str
    unit_price: str
    line_total: str


@dataclass
class QuoteTotals:
    subtotal_excl_vat: str
    vat_rate: str
    vat_amount: str
    total_incl_vat: str


@dataclass
class QuoteBuyer:
    company_name: str
    contact_person: str
    email: str
    phone: str
    address: str


@dataclass
class QuoteSeller:
    company_name: str
    registration_number: str
    vat_number: str
    email: str
    phone: str
    address: str


@dataclass
class QuoteDocument:
    quote_number: str
    rfq_id: str
    rfq_title: str
    issue_date: str
    validity_days: int
    delivery_days: int
    payment_terms: str
    submission_method: str
    buyer: QuoteBuyer
    seller: QuoteSeller
    items: List[QuoteItem]
    totals: QuoteTotals
    notes: List[str]
    source_rfq: Dict[str, Any]


class QuoteEngine:
    @classmethod
    def build_quote_from_rfq(
        cls,
        rfq: Dict[str, Any],
        company_profile: Optional[Dict[str, Any]] = None,
        margin_rate: Any = DEFAULT_MARGIN_RATE,
        vat_rate: Any = DEFAULT_VAT_RATE,
        validity_days: int = DEFAULT_VALIDITY_DAYS,
        delivery_days: int = DEFAULT_DELIVERY_DAYS,
    ) -> Dict[str, Any]:
        if not isinstance(rfq, dict):
            raise ValueError("RFQ must be a dictionary.")

        seller_profile = cls._build_seller_profile(company_profile or {})
        buyer_profile = cls._build_buyer_profile(rfq)

        margin_rate_decimal = _to_decimal(margin_rate, str(DEFAULT_MARGIN_RATE))
        if margin_rate_decimal < 0:
            margin_rate_decimal = DEFAULT_MARGIN_RATE

        vat_rate_decimal = _to_decimal(vat_rate, str(DEFAULT_VAT_RATE))
        if vat_rate_decimal < 0:
            vat_rate_decimal = DEFAULT_VAT_RATE

        rfq_id = _extract_first_non_empty(rfq, ["rfq_id", "id", "tender_id", "notice_id"], default="")
        rfq_title = _extract_first_non_empty(rfq, ["title", "tender_title", "description"], default="Quotation")
        submission_method = _extract_first_non_empty(
            rfq,
            ["submission_method", "submission_mode", "delivery_method"],
            default="unknown",
        )

        quote_number = cls._generate_quote_number(rfq_id=rfq_id)
        issue_date = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")

        raw_items = _normalise_line_items(rfq)
        rfq_estimated_total = _extract_first_number(
            rfq,
            ["estimated_value", "estimated_total", "budget", "budget_total", "value", "amount"],
            default=Decimal("0.00"),
        )

        quote_items: List[QuoteItem] = []
        subtotal = Decimal("0.00")

        for item in raw_items:
            quantity = _to_decimal(item.get("quantity"), "1")
            if quantity <= 0:
                quantity = Decimal("1")

            unit_price = _resolve_unit_price(
                item=item,
                rfq_estimated_total=rfq_estimated_total,
                fallback_margin_rate=margin_rate_decimal,
                total_items_count=len(raw_items),
            )

            line_total = (quantity * unit_price).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            subtotal += line_total

            quote_items.append(
                QuoteItem(
                    line_number=_safe_int(item.get("line_number"), 0),
                    description=_safe_str(item.get("description"), "Supply item"),
                    unit=_safe_str(item.get("unit"), "Each"),
                    quantity=str(quantity.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
                    unit_price=str(unit_price),
                    line_total=str(line_total),
                )
            )

        vat_amount = (subtotal * vat_rate_decimal).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        total_incl_vat = (subtotal + vat_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        notes: List[str] = [
            f"Quotation validity: {validity_days} days from date of issue.",
            f"Estimated delivery period: {delivery_days} days from official order or appointment.",
            "Pricing is subject to final confirmation against the buyer's full RFQ documents and specifications.",
        ]

        document = QuoteDocument(
            quote_number=quote_number,
            rfq_id=rfq_id,
            rfq_title=rfq_title,
            issue_date=issue_date,
            validity_days=validity_days,
            delivery_days=delivery_days,
            payment_terms="Payment due within 30 days from statement unless otherwise agreed in writing.",
            submission_method=submission_method,
            buyer=buyer_profile,
            seller=seller_profile,
            items=quote_items,
            totals=QuoteTotals(
                subtotal_excl_vat=str(subtotal.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
                vat_rate=str(vat_rate_decimal.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
                vat_amount=str(vat_amount),
                total_incl_vat=str(total_incl_vat),
            ),
            notes=notes,
            source_rfq=deepcopy(rfq),
        )

        quote_dict = asdict(document)
        quote_dict["quote_generated"] = True
        quote_dict["currency"] = "ZAR"
        quote_dict["margin_rate"] = str(margin_rate_decimal.quantize(TWOPLACES, rounding=ROUND_HALF_UP))
        return quote_dict

    @classmethod
    def _build_buyer_profile(cls, rfq: Dict[str, Any]) -> QuoteBuyer:
        company_name = _extract_first_non_empty(
            rfq,
            ["buyer_name", "department", "entity_name", "organisation", "organization", "issuer"],
            default="Buyer / Issuing Entity",
        )
        contact_person = _extract_first_non_empty(
            rfq,
            ["contact_person", "buyer_contact_person", "contact_name"],
            default="Procurement Office",
        )
        email = _extract_first_non_empty(
            rfq,
            ["buyer_email", "contact_email", "email"],
            default="",
        )
        phone = _extract_first_non_empty(
            rfq,
            ["buyer_phone", "contact_phone", "phone"],
            default="",
        )
        address = _extract_first_non_empty(
            rfq,
            ["delivery_location", "buyer_address", "address", "physical_address"],
            default="South Africa",
        )

        return QuoteBuyer(
            company_name=company_name,
            contact_person=contact_person,
            email=email,
            phone=phone,
            address=address,
        )

    @classmethod
    def _build_seller_profile(cls, company_profile: Dict[str, Any]) -> QuoteSeller:
        return QuoteSeller(
            company_name=_extract_first_non_empty(
                company_profile,
                ["company_name", "name"],
                default="Lechesa Manaba Consulting and Projects (Pty) Ltd",
            ),
            registration_number=_extract_first_non_empty(
                company_profile,
                ["registration_number", "company_registration", "reg_no"],
                default="2012/159509/07",
            ),
            vat_number=_extract_first_non_empty(
                company_profile,
                ["vat_number", "vat_no"],
                default="4260295953",
            ),
            email=_extract_first_non_empty(
                company_profile,
                ["email", "company_email"],
                default="lechesam@me.com",
            ),
            phone=_extract_first_non_empty(
                company_profile,
                ["phone", "telephone", "company_phone"],
                default="0826338492",
            ),
            address=_extract_first_non_empty(
                company_profile,
                ["address", "physical_address"],
                default="1787 Dube Street, Batho Location, Bloemfontein, South Africa",
            ),
        )

    @classmethod
    def _generate_quote_number(cls, rfq_id: str = "") -> str:
        date_part = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d")
        suffix = rfq_id.strip() if rfq_id else uuid4().hex[:6].upper()
        suffix = "".join(ch for ch in suffix if ch.isalnum())[:12] or uuid4().hex[:6].upper()
        return f"LMCP-{date_part}-{suffix}"


def build_quote_from_rfq(
    rfq: Dict[str, Any],
    company_profile: Optional[Dict[str, Any]] = None,
    margin_rate: Any = DEFAULT_MARGIN_RATE,
    vat_rate: Any = DEFAULT_VAT_RATE,
    validity_days: int = DEFAULT_VALIDITY_DAYS,
    delivery_days: int = DEFAULT_DELIVERY_DAYS,
) -> Dict[str, Any]:
    return QuoteEngine.build_quote_from_rfq(
        rfq=rfq,
        company_profile=company_profile,
        margin_rate=margin_rate,
        vat_rate=vat_rate,
        validity_days=validity_days,
        delivery_days=delivery_days,
    )
