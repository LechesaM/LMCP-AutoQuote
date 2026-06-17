from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).replace(",", "").strip())
        except Exception:
            return None


def _fmt_money(value: Any, currency: str = "ZAR") -> str:
    amount = _coerce_float(value)
    if amount is None:
        return ""
    return f"{currency} {amount:,.2f}"


def _build_pdf(
    pdf_path: Path,
    *,
    buyer_form_payload: Dict[str, Any],
    populated_form_rows: List[Dict[str, Any]],
) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "LMCPTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "LMCPMeta",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.black,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "LMCPBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.5,
        textColor=colors.black,
    )
    small_style = ParagraphStyle(
        "LMCPSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.black,
    )

    summary = _safe_dict(buyer_form_payload.get("summary"))
    currency = _clean(buyer_form_payload.get("currency") or "ZAR")

    story = []
    story.append(Paragraph("Buyer Pricing Schedule", title_style))
    story.append(Paragraph(f"<b>Buyer:</b> {_clean(buyer_form_payload.get('buyer_name'))}", meta_style))
    story.append(Paragraph(f"<b>RFQ Number:</b> {_clean(buyer_form_payload.get('rfq_number'))}", meta_style))
    story.append(Paragraph(f"<b>Document Title:</b> {_clean(buyer_form_payload.get('document_title'))}", meta_style))
    story.append(Paragraph(f"<b>Quote Reference:</b> {_clean(buyer_form_payload.get('quote_reference'))}", meta_style))
    story.append(Spacer(1, 4 * mm))

    summary_table = Table(
        [
            ["Subtotal", _fmt_money(summary.get("subtotal"), currency)],
            ["VAT Amount", _fmt_money(summary.get("vat_amount"), currency)],
            ["Grand Total", _fmt_money(summary.get("grand_total"), currency)],
            ["Priced Rows", str(summary.get("priced_rows") or 0)],
            ["Pending Rows", str(summary.get("pending_rows") or 0)],
            ["Review Rows Held Back", str(summary.get("review_rows_held_back") or 0)],
        ],
        colWidths=[48 * mm, 36 * mm],
        hAlign="LEFT",
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#D9E2F3")),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9EB6D8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C5D1E3")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 5 * mm))

    header = [
        Paragraph("<b>Item</b>", small_style),
        Paragraph("<b>Description</b>", small_style),
        Paragraph("<b>Specification</b>", small_style),
        Paragraph("<b>Unit</b>", small_style),
        Paragraph("<b>Qty</b>", small_style),
        Paragraph("<b>Unit Price</b>", small_style),
        Paragraph("<b>Total</b>", small_style),
    ]
    rows = [header]

    for row in _safe_list(populated_form_rows):
        r = _safe_dict(row)
        rows.append(
            [
                Paragraph(_clean(r.get("buyer_item_number")), body_style),
                Paragraph(_clean(r.get("description")), body_style),
                Paragraph(_clean(r.get("specification")), body_style),
                Paragraph(_clean(r.get("unit")), body_style),
                Paragraph(_clean(r.get("quantity")), body_style),
                Paragraph(_fmt_money(r.get("unit_price"), currency), body_style),
                Paragraph(_fmt_money(r.get("line_total"), currency), body_style),
            ]
        )

    table = Table(
        rows,
        colWidths=[12 * mm, 48 * mm, 54 * mm, 16 * mm, 16 * mm, 20 * mm, 22 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9EB6D8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2F3")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (3, 1), (6, -1), "CENTER"),
            ]
        )
    )
    story.append(table)

    doc.build(story)


def build_buyer_pdf_renderer_output(
    buyer_form_payload: Dict[str, Any],
    *,
    populated_form_rows: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    buyer_form_payload = _safe_dict(buyer_form_payload)
    metadata = _safe_dict(metadata)
    populated_form_rows = _safe_list(populated_form_rows) or _safe_list(buyer_form_payload.get("items"))

    rfq_number = _clean(buyer_form_payload.get("rfq_number") or metadata.get("buyer_rfq_number") or "RFQ")
    safe_ref = "".join(ch if ch.isalnum() else "_" for ch in rfq_number).strip("_") or "RFQ"
    output_dir = Path(_clean(metadata.get("pdf_output_dir") or str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "generated_quotes")))
    output_path = output_dir / f"{safe_ref}_buyer_pricing_schedule.pdf"

    _build_pdf(
        output_path,
        buyer_form_payload=buyer_form_payload,
        populated_form_rows=populated_form_rows,
    )

    ready_rows = 0
    pending_rows = 0
    rendered_item_numbers: List[int] = []
    pending_item_numbers: List[int] = []

    for row in populated_form_rows:
        data = _safe_dict(row)
        status = _clean(data.get("form_population_status")).lower()
        item_number = data.get("item_number") if "item_number" in data else data.get("buyer_item_number")
        if status == "ready_for_pdf":
            ready_rows += 1
            if isinstance(item_number, int):
                rendered_item_numbers.append(item_number)
        else:
            pending_rows += 1
            if isinstance(item_number, int):
                pending_item_numbers.append(item_number)

    return {
        "buyer_pdf_renderer": {
            "input_rows": len(populated_form_rows),
            "render_ready_rows": ready_rows,
            "render_pending_rows": pending_rows,
            "rendered_item_numbers": rendered_item_numbers,
            "pending_item_numbers": pending_item_numbers,
            "pdf_output_path": str(output_path),
        },
        "rendered_buyer_pdf_path": str(output_path),
        "buyer_pdf_render_ready_count": ready_rows,
        "buyer_pdf_render_pending_count": pending_rows,
    }


def attach_buyer_pdf_renderer_to_record(
    record: Dict[str, Any],
    *,
    buyer_form_payload_key: str = "buyer_form_payload",
    populated_form_rows_key: str = "populated_form_rows",
    metadata_key: str = "metadata",
) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    result = build_buyer_pdf_renderer_output(
        _safe_dict(payload.get(buyer_form_payload_key)),
        populated_form_rows=_safe_list(payload.get(populated_form_rows_key)),
        metadata=_safe_dict(payload.get(metadata_key)),
    )
    payload.update(result)
    return payload


if __name__ == "__main__":
    sample_payload = {
        "buyer_name": "STELLENBOSCH MUNICIPALITY",
        "rfq_number": "B/SM 110/26",
        "document_title": "SUPPLY AND DELIVERY OF STATIONERY",
        "quote_reference": "B/SM 110/26",
        "currency": "ZAR",
        "prices_include_vat": True,
        "vat_rate": 15.0,
        "summary": {
            "subtotal": 210800.0,
            "vat_amount": 31620.0,
            "grand_total": 242420.0,
            "priced_rows": 208,
            "pending_rows": 0,
            "review_rows_held_back": 58,
        },
    }
    sample_rows = [
        {
            "buyer_item_number": 1,
            "description": "Stapler for office use | Uses 26/6 staples",
            "specification": "Uses 26/6 staples",
            "unit": "Each",
            "quantity": 100.0,
            "unit_price": 32.5,
            "line_total": 3250.0,
            "form_population_status": "ready_for_pdf",
        }
    ]
    result = build_buyer_pdf_renderer_output(sample_payload, populated_form_rows=sample_rows)
    print(result)
