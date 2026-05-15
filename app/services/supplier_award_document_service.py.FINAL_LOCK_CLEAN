from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return round(float(value), 2)
    except Exception:
        return default


def _sanitize_part(value: Any, fallback: str) -> str:
    raw = _safe_str(value)
    if not raw or raw in {"-", "N/A", "UNKNOWN", "UNKNOWN-RFQ", "UNKNOWN-QUOTE"}:
        return fallback

    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in raw)
    cleaned = cleaned.strip("-_")
    return cleaned or fallback


def _locked_context(payload: Dict[str, Any]) -> Dict[str, str]:
    submission_pack = payload.get("submission_pack") or {}
    quote_pack = payload.get("quote_pack") or {}
    rfq = payload.get("rfq") or {}
    buyer = payload.get("buyer") or {}

    locked_rfq = (
        _safe_str(payload.get("_locked_buyer_rfq_number"))
        or _safe_str(payload.get("buyer_rfq_number"))
        or _safe_str(payload.get("rfq_number"))
        or _safe_str(payload.get("reference_number"))
        or _safe_str(payload.get("document_number"))
        or _safe_str(submission_pack.get("buyer_rfq_number"))
        or _safe_str(submission_pack.get("document_number"))
        or _safe_str(quote_pack.get("buyer_rfq_number"))
        or _safe_str(rfq.get("buyer_rfq_number"))
        or _safe_str(rfq.get("rfq_number"))
        or _safe_str(buyer.get("rfq_number"))
    )

    if not locked_rfq:
        raise ValueError("CRITICAL: buyer_rfq_number missing before supplier award stage")

    locked_quote = (
        _safe_str(payload.get("quote_number"))
        or _safe_str(payload.get("lmcp_quote_number"))
        or _safe_str(submission_pack.get("quote_number"))
        or _safe_str(quote_pack.get("quote_number"))
        or f"LMCP-{locked_rfq}"
    )

    if not locked_quote:
        raise ValueError("CRITICAL: quote_number missing before supplier award stage")

    month_key = datetime.utcnow().strftime("%Y-%m")
    safe_rfq = _sanitize_part(locked_rfq, "UNKNOWN-RFQ")
    safe_quote = _sanitize_part(locked_quote, "UNKNOWN-QUOTE")
    folder_name = f"{safe_rfq}__{safe_quote}"
    folder = Path("monthly_quotes") / month_key / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    return {
        "locked_rfq": locked_rfq,
        "locked_quote": locked_quote,
        "month_key": month_key,
        "safe_rfq": safe_rfq,
        "safe_quote": safe_quote,
        "folder_name": folder_name,
        "folder_path": str(folder),
    }

    if not locked_rfq:
        raise ValueError("CRITICAL: buyer_rfq_number missing before supplier award stage")

    locked_quote = (
        _safe_str(payload.get("quote_number"))
        or _safe_str(payload.get("lmcp_quote_number"))
        or _safe_str(submission_pack.get("quote_number"))
        or _safe_str(quote_pack.get("quote_number"))
        or f"LMCP-{locked_rfq}"
    )
    
    if not locked_quote:
        raise ValueError("CRITICAL: quote_number missing before supplier award stage")

    month_key = datetime.utcnow().strftime("%Y-%m")
    safe_rfq = _sanitize_part(locked_rfq, "UNKNOWN-RFQ")
    safe_quote = _sanitize_part(locked_quote, "UNKNOWN-QUOTE")
    folder_name = f"{safe_rfq}__{safe_quote}"
    folder = Path("monthly_quotes") / month_key / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    return {
        "locked_rfq": locked_rfq,
        "locked_quote": locked_quote,
        "month_key": month_key,
        "safe_rfq": safe_rfq,
        "safe_quote": safe_quote,
        "folder_name": folder_name,
        "folder_path": str(folder),
    }


def _apply_locked_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    ctx = _locked_context(payload)

    payload["_locked_buyer_rfq_number"] = ctx["locked_rfq"]
    payload["buyer_rfq_number"] = ctx["locked_rfq"]
    payload["rfq_number"] = ctx["locked_rfq"]
    payload["reference_number"] = ctx["locked_rfq"]
    payload["document_number"] = ctx["locked_rfq"]
    payload["quote_number"] = ctx["locked_quote"]

    payload["quote_folder"] = ctx["folder_path"]
    payload["monthly_quote_folder"] = ctx["folder_path"]
    payload["folder_path"] = ctx["folder_path"]
    payload["folder_name"] = ctx["folder_name"]

    submission_pack = payload.get("submission_pack") or {}
    if isinstance(submission_pack, dict):
        submission_pack["buyer_rfq_number"] = ctx["locked_rfq"]
        submission_pack["document_number"] = ctx["locked_rfq"]
        submission_pack["quote_number"] = ctx["locked_quote"]
        submission_pack["folder_path"] = ctx["folder_path"]
        payload["submission_pack"] = submission_pack

    return payload


def _folder(payload: Dict[str, Any]) -> Path:
    payload = _apply_locked_context(payload)
    folder_path = payload.get("monthly_quote_folder") or payload.get("quote_folder") or payload.get("folder_path")
    folder = Path(folder_path)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _company_details(payload: Dict[str, Any]) -> Dict[str, str]:
    seller = payload.get("seller") or payload.get("company") or {}

    return {
        "company_name": _safe_str(seller.get("company_name"), "Lechesa Manaba Consulting and Projects (Pty) Ltd"),
        "address": _safe_str(seller.get("address"), "1787 Dube Street, Batho Location, Bloemfontein, 9323"),
        "phone": _safe_str(seller.get("phone"), "0826338492"),
        "email": _safe_str(seller.get("email"), "lechesam@me.com"),
        "registration_number": _safe_str(seller.get("registration_number"), "2012/159509/07"),
        "vat_number": _safe_str(seller.get("vat_number"), "4260295953"),
    }


def _buyer_details(payload: Dict[str, Any]) -> Dict[str, str]:
    payload = _apply_locked_context(payload)
    rfq = payload.get("rfq") or payload
    buyer = rfq.get("buyer") or payload.get("buyer") or {}

    return {
        "buyer_name": _safe_str(
            buyer.get("name")
            or buyer.get("company_name")
            or rfq.get("buyer_name")
            or payload.get("buyer_name"),
            "Buyer / Issuing Entity",
        ),
        "buyer_rfq_number": _safe_str(
            payload.get("_locked_buyer_rfq_number")
            or rfq.get("buyer_rfq_number")
            or payload.get("buyer_rfq_number")
            or payload.get("rfq_number"),
            "UNKNOWN-RFQ",
        ),
    }


def _items_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    awarded_supplier = payload.get("awarded_supplier") or {}
    supplier_items = awarded_supplier.get("items") or []
    if supplier_items:
        return supplier_items

    rfq = payload.get("rfq") or payload
    items = rfq.get("items") or payload.get("items") or []
    normalized: List[Dict[str, Any]] = []

    for item in items:
        if isinstance(item, dict):
            normalized.append(
                {
                    "description": _safe_str(
                        item.get("description")
                        or item.get("item_description")
                        or item.get("name")
                        or item.get("title"),
                        "Item",
                    ),
                    "quantity": item.get("quantity") or item.get("qty") or 1,
                    "unit_price": item.get("unit_price") or item.get("rate") or 0,
                    "line_total": item.get("line_total") or item.get("total") or 0,
                }
            )
        else:
            normalized.append(
                {
                    "description": _safe_str(item, "Item"),
                    "quantity": 1,
                    "unit_price": 0,
                    "line_total": 0,
                }
            )

    return normalized


def _draw_wrapped_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    line_height: float = 12,
    font_name: str = "Helvetica",
    font_size: int = 10,
) -> float:
    words = (text or "").split()
    current = ""
    c.setFont(font_name, font_size)

    for word in words:
        test = f"{current} {word}".strip()
        if c.stringWidth(test, font_name, font_size) <= max_width:
            current = test
        else:
            c.drawString(x, y, current)
            y -= line_height
            current = word

    if current:
        c.drawString(x, y, current)
        y -= line_height

    return y


def generate_supplier_award_summary_pdf(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _apply_locked_context(payload)
    folder = _folder(payload)
    award = payload.get("supplier_award") or {}
    awarded_supplier = payload.get("awarded_supplier") or award.get("awarded_supplier") or {}
    runner_up = payload.get("runner_up_supplier") or award.get("runner_up_supplier") or {}
    ranked = award.get("ranked_suppliers") or []

    company = _company_details(payload)
    buyer = _buyer_details(payload)

    award_pdf_path = folder / "supplier_award_summary.pdf"

    c = canvas.Canvas(str(award_pdf_path), pagesize=A4)
    width, height = A4

    left = 18 * mm
    right = width - (18 * mm)
    y = height - (18 * mm)

    c.setFont("Helvetica-Bold", 15)
    c.drawString(left, y, "SUPPLIER AWARD SUMMARY")
    y -= 8 * mm

    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 6 * mm
    c.drawString(left, y, f"Company: {company['company_name']}")
    y -= 6 * mm
    c.drawString(left, y, f"Buyer RFQ Number: {buyer['buyer_rfq_number']}")
    y -= 6 * mm
    c.drawString(left, y, f"Buyer: {buyer['buyer_name']}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Award Decision")
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Award Status: {_safe_str(award.get('award_status'), 'N/A')}")
    y -= 6 * mm
    c.drawString(left, y, f"Auto Award: {'Yes' if award.get('auto_award') else 'No'}")
    y -= 6 * mm
    c.drawString(left, y, f"Award Confidence: {_safe_str(award.get('award_confidence'), '0.00')}")
    y -= 8 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Selected Supplier")
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Supplier: {_safe_str(awarded_supplier.get('supplier_name'), 'N/A')}")
    y -= 6 * mm
    c.drawString(left, y, f"Quote Number: {_safe_str(awarded_supplier.get('quote_number'), 'N/A')}")
    y -= 6 * mm
    c.drawString(left, y, f"Quote Date: {_safe_str(awarded_supplier.get('quote_date'), 'N/A')}")
    y -= 6 * mm
    c.drawString(left, y, f"Total Incl VAT: R {_safe_float(awarded_supplier.get('total_incl_vat')):,.2f}")
    y -= 6 * mm
    c.drawString(left, y, f"Lead Time: {_safe_str(awarded_supplier.get('lead_time'), 'N/A')}")
    y -= 8 * mm

    if runner_up:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left, y, "Runner-Up Supplier")
        y -= 6 * mm

        c.setFont("Helvetica", 10)
        c.drawString(left, y, f"Supplier: {_safe_str(runner_up.get('supplier_name'), 'N/A')}")
        y -= 6 * mm
        c.drawString(left, y, f"Total Incl VAT: R {_safe_float(runner_up.get('total_incl_vat')):,.2f}")
        y -= 8 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Award Reason")
    y -= 6 * mm

    reason = _safe_str(award.get("award_reason"), "No detailed reason recorded.")
    y = _draw_wrapped_text(c, reason, left, y, right - left, line_height=12, font_name="Helvetica", font_size=10)
    y -= 4 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Supplier Ranking")
    y -= 7 * mm

    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Rank")
    c.drawString(left + 20 * mm, y, "Supplier")
    c.drawString(left + 95 * mm, y, "Total")
    c.drawString(left + 125 * mm, y, "Score")
    c.drawString(left + 150 * mm, y, "Compliant")
    y -= 5 * mm

    c.setFont("Helvetica", 9)
    for idx, row in enumerate(ranked[:10], start=1):
        if y < 30 * mm:
            c.showPage()
            y = height - (18 * mm)
            c.setFont("Helvetica", 9)

        c.drawString(left, y, str(idx))
        c.drawString(left + 20 * mm, y, _safe_str(row.get("supplier_name"), "N/A")[:42])
        c.drawString(left + 95 * mm, y, f"R {_safe_float(row.get('total_incl_vat')):,.2f}")
        c.drawString(left + 125 * mm, y, f"{_safe_float(row.get('total_score')):.3f}")
        c.drawString(left + 150 * mm, y, "Yes" if row.get("compliant") else "No")
        y -= 5 * mm

    c.save()

    payload["supplier_award_summary_pdf"] = str(award_pdf_path)
    return payload


def generate_supplier_purchase_order_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _apply_locked_context(payload)
    folder = _folder(payload)
    company = _company_details(payload)
    buyer = _buyer_details(payload)
    awarded_supplier = payload.get("awarded_supplier") or {}
    items = _items_from_payload(payload)

    po_number = _safe_str(
        payload.get("supplier_po_number"),
        f"LMCP-PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    )

    total = _safe_float(awarded_supplier.get("total_incl_vat"))
    vat_amount = _safe_float(awarded_supplier.get("vat_amount"))
    subtotal = round(total - vat_amount, 2) if total and vat_amount else total

    po_data = {
        "po_number": po_number,
        "po_date": datetime.now().strftime("%Y-%m-%d"),
        "buyer_rfq_number": buyer["buyer_rfq_number"],
        "buyer_name": buyer["buyer_name"],
        "issuing_company": company,
        "selected_supplier": {
            "supplier_name": _safe_str(awarded_supplier.get("supplier_name")),
            "quote_number": _safe_str(awarded_supplier.get("quote_number")),
            "quote_date": _safe_str(awarded_supplier.get("quote_date")),
            "supplier_email": _safe_str(awarded_supplier.get("email")),
            "lead_time": _safe_str(awarded_supplier.get("lead_time")),
        },
        "commercials": {
            "subtotal": subtotal,
            "vat_amount": vat_amount,
            "total_incl_vat": total,
            "currency": _safe_str(awarded_supplier.get("currency"), "ZAR"),
        },
        "items": items,
        "status": "draft",
    }

    po_json_path = folder / "supplier_purchase_order.json"
    po_json_path.write_text(json.dumps(po_data, indent=2, ensure_ascii=False), encoding="utf-8")

    payload["supplier_purchase_order"] = po_data
    payload["supplier_purchase_order_json"] = str(po_json_path)
    return payload


def generate_supplier_purchase_order_pdf(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _apply_locked_context(payload)
    folder = _folder(payload)
    po = payload.get("supplier_purchase_order") or {}
    company = po.get("issuing_company") or _company_details(payload)
    supplier = po.get("selected_supplier") or {}
    items = po.get("items") or []
    commercials = po.get("commercials") or {}

    po_pdf_path = folder / "supplier_purchase_order.pdf"

    c = canvas.Canvas(str(po_pdf_path), pagesize=A4)
    width, height = A4

    left = 18 * mm
    right = width - (18 * mm)
    y = height - (18 * mm)

    c.setFont("Helvetica-Bold", 15)
    c.drawString(left, y, "SUPPLIER PURCHASE ORDER")
    y -= 8 * mm

    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"PO Number: {_safe_str(po.get('po_number'))}")
    y -= 6 * mm
    c.drawString(left, y, f"PO Date: {_safe_str(po.get('po_date'))}")
    y -= 6 * mm
    c.drawString(left, y, f"Buyer RFQ Number: {_safe_str(po.get('buyer_rfq_number'))}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Issued By")
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(left, y, _safe_str(company.get("company_name")))
    y -= 5 * mm
    c.drawString(left, y, _safe_str(company.get("address")))
    y -= 5 * mm
    c.drawString(left, y, f"Phone: {_safe_str(company.get('phone'))}")
    y -= 5 * mm
    c.drawString(left, y, f"Email: {_safe_str(company.get('email'))}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Awarded Supplier")
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Supplier: {_safe_str(supplier.get('supplier_name'))}")
    y -= 5 * mm
    c.drawString(left, y, f"Quote Number: {_safe_str(supplier.get('quote_number'))}")
    y -= 5 * mm
    c.drawString(left, y, f"Quote Date: {_safe_str(supplier.get('quote_date'))}")
    y -= 5 * mm
    c.drawString(left, y, f"Supplier Email: {_safe_str(supplier.get('supplier_email'))}")
    y -= 5 * mm
    c.drawString(left, y, f"Lead Time: {_safe_str(supplier.get('lead_time'))}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Items")
    y -= 7 * mm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(left, y, "No.")
    c.drawString(left + 12 * mm, y, "Description")
    c.drawString(left + 110 * mm, y, "Qty")
    c.drawString(left + 130 * mm, y, "Unit Price")
    c.drawString(left + 160 * mm, y, "Line Total")
    y -= 5 * mm

    c.setFont("Helvetica", 8)
    for idx, item in enumerate(items, start=1):
        if y < 35 * mm:
            c.showPage()
            y = height - (18 * mm)
            c.setFont("Helvetica", 8)

        desc = _safe_str(item.get("description"), "Item")
        qty = _safe_float(item.get("quantity"), 0)
        unit_price = _safe_float(item.get("unit_price"), 0)
        line_total = _safe_float(item.get("line_total"), 0)

        c.drawString(left, y, str(idx))
        c.drawString(left + 12 * mm, y, desc[:58])
        c.drawRightString(left + 125 * mm, y, f"{qty:,.2f}")
        c.drawRightString(left + 155 * mm, y, f"R {unit_price:,.2f}")
        c.drawRightString(right, y, f"R {line_total:,.2f}")
        y -= 5 * mm

    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(right, y, f"Subtotal: R {_safe_float(commercials.get('subtotal')):,.2f}")
    y -= 5 * mm
    c.drawRightString(right, y, f"VAT: R {_safe_float(commercials.get('vat_amount')):,.2f}")
    y -= 5 * mm
    c.drawRightString(right, y, f"Total Incl VAT: R {_safe_float(commercials.get('total_incl_vat')):,.2f}")

    y -= 12 * mm
    c.setFont("Helvetica", 9)
    c.drawString(left, y, "Status: DRAFT PURCHASE ORDER - SUBJECT TO FINAL INTERNAL APPROVAL")

    c.save()

    payload["supplier_purchase_order_pdf"] = str(po_pdf_path)
    return payload


def generate_supplier_award_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _apply_locked_context(payload)
    payload = generate_supplier_award_summary_pdf(payload)
    payload = generate_supplier_purchase_order_json(payload)
    payload = generate_supplier_purchase_order_pdf(payload)
    return payload
