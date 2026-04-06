from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _money(zar: float) -> str:
    return f"R{zar:,.2f}".replace(",", " ")


def _normalize(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_title(op: Dict[str, Any]) -> str:
    v = op.get("title")
    if isinstance(v, str) and v.strip():
        return v.strip()

    tender = op.get("tender")
    if isinstance(tender, dict):
        t = tender.get("title") or tender.get("description")
        if isinstance(t, str) and t.strip():
            return t.strip()

    for k in ["name", "description", "summary", "ocid"]:
        v = op.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return "Opportunity"


def extract_reference(op: Dict[str, Any]) -> str:
    for k in ["reference", "ref", "tenderNumber", "tender_number", "ocid", "id"]:
        v = op.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)):
            return str(v)
    return "N/A"


def extract_buyer(op: Dict[str, Any]) -> str:
    buyer = op.get("buyer")
    if isinstance(buyer, dict):
        name = buyer.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

    for k in ["department", "entity", "procuring_entity", "procuringEntity", "buyer_name"]:
        v = op.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return "Client / Procuring Entity"


def classify_scope(op: Dict[str, Any]) -> str:
    blob = str(op).lower()
    if any(x in blob for x in ["plumbing", "reticulation", "pipeline", "water", "sewer", "wastewater"]):
        return "Plumbing & Water Works"
    if any(x in blob for x in ["civil", "road", "stormwater", "paving", "earthworks", "asphalt", "kerb", "culvert"]):
        return "Civil & Roads"
    if any(x in blob for x in ["electrical", "solar", "inverter", "generator", "cable", "db board"]):
        return "Electrical & Power"
    if any(x in blob for x in ["supply", "delivery", "supply and delivery", "materials"]):
        return "Supply & Delivery"
    if any(x in blob for x in ["building", "maintenance", "refurbishment", "renovation", "painting", "tiling"]):
        return "General Building & Maintenance"
    return "General Services"


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            s = x.strip().replace(" ", "").replace(",", "")
            if not s:
                return None
            return float(s)
    except Exception:
        return None
    return None


def extract_base_amount_from_ocds(op: Dict[str, Any]) -> Optional[float]:
    """
    Pull a usable amount from typical OCDS structures (best-effort).
    """
    if not isinstance(op, dict):
        return None

    # tender.value.amount
    tender = op.get("tender")
    if isinstance(tender, dict):
        value = tender.get("value")
        if isinstance(value, dict):
            amt = _to_float(value.get("amount"))
            if amt and amt > 0:
                return amt

    # planning.budget.amount / planning.budget.amount.amount
    planning = op.get("planning")
    if isinstance(planning, dict):
        budget = planning.get("budget")
        if isinstance(budget, dict):
            # sometimes budget.amount is a dict
            amt = _to_float(budget.get("amount"))
            if amt and amt > 0:
                return amt
            amt_obj = budget.get("amount")
            if isinstance(amt_obj, dict):
                amt2 = _to_float(amt_obj.get("amount"))
                if amt2 and amt2 > 0:
                    return amt2

    # top-level value or amount fields (rare)
    for k in ["amount", "value", "estimated_value", "estimatedValue"]:
        v = op.get(k)
        if isinstance(v, dict):
            amt = _to_float(v.get("amount"))
            if amt and amt > 0:
                return amt
        else:
            amt = _to_float(v)
            if amt and amt > 0:
                return amt

    return None


def _fallback_base_amount(scope: str) -> float:
    """
    Configurable fallback estimates when the opportunity has no usable value/budget.
    Set these in docker-compose env later if you want.
    """
    def _env_money(name: str, default: float) -> float:
        v = _to_float(os.getenv(name))
        return float(v) if v and v > 0 else default

    if scope == "Supply & Delivery":
        return _env_money("DEFAULT_BASE_SUPPLY", 150_000.0)
    if scope == "Civil & Roads":
        return _env_money("DEFAULT_BASE_CIVIL", 750_000.0)
    if scope == "Plumbing & Water Works":
        return _env_money("DEFAULT_BASE_PLUMBING", 450_000.0)
    if scope == "Electrical & Power":
        return _env_money("DEFAULT_BASE_ELECTRICAL", 250_000.0)
    if scope == "General Building & Maintenance":
        return _env_money("DEFAULT_BASE_BUILDING", 350_000.0)
    return _env_money("DEFAULT_BASE_GENERAL", 200_000.0)


def build_priced_items(opportunity: Dict[str, Any], base_amount: Optional[float] = None) -> Tuple[str, float, List[Dict[str, Any]]]:
    """
    Smart pricing: decides scope, picks base amount (from OCDS or fallback),
    and allocates it into line items with rates.
    """
    scope = classify_scope(opportunity)

    # Determine base amount
    base = base_amount if (base_amount and base_amount > 0) else extract_base_amount_from_ocds(opportunity)
    if not base or base <= 0:
        base = _fallback_base_amount(scope)

    # Configurable delivery percentage for supply & delivery
    delivery_pct = _to_float(os.getenv("DELIVERY_PCT")) or 7.5  # default 7.5%
    delivery_pct = float(delivery_pct)

    items: List[Dict[str, Any]] = []

    if scope == "Supply & Delivery":
        delivery_value = base * (delivery_pct / 100.0)
        supply_value = max(0.0, base - delivery_value)
        items = [
            {"description": "Supply of goods as per RFQ specifications", "qty": 1, "unit": "Lot", "rate": round(supply_value, 2)},
            {"description": "Delivery to site (distributed logistics)", "qty": 1, "unit": "Lot", "rate": round(delivery_value, 2)},
        ]
        return scope, base, items

    if scope == "Civil & Roads":
        # Typical split: prelims 12%, labour/plant 45%, materials 43%
        items = [
            {"description": "Site establishment & preliminaries", "qty": 1, "unit": "Lot", "rate": round(base * 0.12, 2)},
            {"description": "Labour, plant & supervision (execution)", "qty": 1, "unit": "Lot", "rate": round(base * 0.45, 2)},
            {"description": "Materials & consumables", "qty": 1, "unit": "Lot", "rate": round(base * 0.43, 2)},
        ]
        return scope, base, items

    if scope == "Plumbing & Water Works":
        # Split: prelims 10%, execution 75%, testing 15%
        items = [
            {"description": "Site establishment, safety file & preliminaries", "qty": 1, "unit": "Lot", "rate": round(base * 0.10, 2)},
            {"description": "Plumbing / water works execution", "qty": 1, "unit": "Lot", "rate": round(base * 0.75, 2)},
            {"description": "Testing, commissioning & handover", "qty": 1, "unit": "Lot", "rate": round(base * 0.15, 2)},
        ]
        return scope, base, items

    if scope == "Electrical & Power":
        # Split: install 85%, testing 15%
        items = [
            {"description": "Electrical installation works", "qty": 1, "unit": "Lot", "rate": round(base * 0.85, 2)},
            {"description": "Testing, CoC & commissioning", "qty": 1, "unit": "Lot", "rate": round(base * 0.15, 2)},
        ]
        return scope, base, items

    # General building / services
    items = [
        {"description": "Site establishment & preliminaries", "qty": 1, "unit": "Lot", "rate": round(base * 0.15, 2)},
        {"description": "Execution of works/services (as per scope)", "qty": 1, "unit": "Lot", "rate": round(base * 0.85, 2)},
    ]
    return scope, base, items


def compute_totals(items: List[Dict[str, Any]], profit_percent: float, vat_percent: float) -> Dict[str, float]:
    subtotal = 0.0
    for it in items:
        qty = float(it.get("qty", 0) or 0)
        rate = float(it.get("rate", 0) or 0)
        subtotal += qty * rate

    profit = subtotal * (profit_percent / 100.0)
    ex_vat = subtotal + profit
    vat = ex_vat * (vat_percent / 100.0)
    total = ex_vat + vat

    return {"subtotal": subtotal, "profit": profit, "ex_vat": ex_vat, "vat": vat, "total": total}


def build_quote_text(
    opportunity: Dict[str, Any],
    *,
    quote_number: str,
    client_email: Optional[str],
    contact_person: Optional[str],
    items: List[Dict[str, Any]],
    profit_percent: float,
    vat_percent: float,
    validity_days: int = 30,
    lead_time_days: int = 14,
    base_amount_used: Optional[float] = None,
) -> Tuple[str, Dict[str, Any]]:
    company_name = os.getenv("COMPANY_NAME", "Lechesa Manaba Consulting and Projects (Pty) Ltd")
    company_reg = os.getenv("COMPANY_REG", "2012/159509/07")
    company_email = os.getenv("COMPANY_EMAIL", "lechesam@me.com")
    company_phone = os.getenv("COMPANY_PHONE", "+27 82 633 8492")
    company_address = os.getenv("COMPANY_ADDRESS", "1787 Dube Street, Batho Location, Bloemfontein, South Africa")

    title = _normalize(extract_title(opportunity))
    ref = _normalize(extract_reference(opportunity))
    buyer = _normalize(extract_buyer(opportunity))
    scope = classify_scope(opportunity)

    totals = compute_totals(items, profit_percent=profit_percent, vat_percent=vat_percent)

    lines: List[str] = []
    lines.append(f"{company_name}")
    lines.append(f"Reg No: {company_reg}")
    lines.append(f"Address: {company_address}")
    lines.append(f"Email: {company_email} | Tel: {company_phone}")
    lines.append("")
    lines.append("QUOTATION")
    lines.append(f"Quote No: {quote_number}")
    lines.append(f"Date: {_now_iso()}")
    lines.append("")
    lines.append(f"Client: {buyer}")
    if contact_person:
        lines.append(f"Attention: {contact_person}")
    if client_email:
        lines.append(f"Client Email: {client_email}")
    lines.append("")
    lines.append(f"RFQ / Reference: {ref}")
    lines.append(f"Opportunity: {title}")
    lines.append(f"Scope Category: {scope}")
    if base_amount_used is not None:
        lines.append(f"Base Amount Used (ex profit, ex VAT): {_money(base_amount_used)}")
    lines.append("")
    lines.append("LINE ITEMS")
    lines.append("-" * 86)
    lines.append(f"{'No':<4} {'Description':<54} {'Qty':>6} {'Unit':<6} {'Rate':>14}")
    lines.append("-" * 86)

    for idx, it in enumerate(items, start=1):
        desc = _normalize(str(it.get("description", "")))[:54]
        qty = float(it.get("qty", 0) or 0)
        unit = _normalize(str(it.get("unit", "Lot")))[:6]
        rate = float(it.get("rate", 0) or 0)
        lines.append(f"{idx:<4} {desc:<54} {qty:>6.2f} {unit:<6} {_money(rate):>14}")

    lines.append("-" * 86)
    lines.append(f"{'Subtotal (ex profit)':<32} {_money(totals['subtotal'])}")
    lines.append(f"{f'Profit ({profit_percent:.0f}%)':<32} {_money(totals['profit'])}")
    lines.append(f"{'Total (ex VAT)':<32} {_money(totals['ex_vat'])}")
    lines.append(f"{f'VAT ({vat_percent:.0f}%)':<32} {_money(totals['vat'])}")
    lines.append(f"{'TOTAL (incl VAT)':<32} {_money(totals['total'])}")
    lines.append("")
    lines.append("COMMERCIAL TERMS")
    lines.append(f"- Validity: {validity_days} days")
    lines.append(f"- Lead time: {lead_time_days} days (subject to official order)")
    lines.append("- Payment terms: As per client SCM / PO terms (or 30 days EOM)")
    lines.append("- Subject to final scope clarification and site conditions (where applicable).")
    lines.append("")
    lines.append("ACCEPTANCE")
    lines.append("Please confirm acceptance by issuing a Purchase Order / Award Letter referencing the Quote No above.")
    lines.append("")
    lines.append("Yours faithfully,")
    lines.append(company_name)

    quote_text = "\n".join(lines)

    meta = {
        "quote_number": quote_number,
        "created_date": _now_iso(),
        "buyer": buyer,
        "reference": ref,
        "title": title,
        "scope_category": scope,
        "profit_percent": profit_percent,
        "vat_percent": vat_percent,
        "base_amount_used": base_amount_used,
        "totals": totals,
    }
    return quote_text, meta
