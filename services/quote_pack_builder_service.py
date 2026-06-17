from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import hashlib
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _coerce_float(value: Any):
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



def _safe_ref_slug(value: Any, max_len: int = 80) -> str:
    raw = _clean(value) or "RFQ"
    base = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_") or "RFQ"
    if len(base) <= max_len:
        return base
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    keep = max_len - (len(digest) + 1)
    if keep < 8:
        keep = 8
    return f"{base[:keep]}_{digest}"

def _build_quote_pack_pdf(
    pdf_path: Path,
    *,
    quote_pack_payload: Dict[str, Any],
    quote_pack_summary: Dict[str, Any],
    rendered_buyer_pdf_path: str,
) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "QPTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=6,
    )
    sub_style = ParagraphStyle(
        "QPSub",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.black,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "QPBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.black,
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
    )

    currency = _clean(quote_pack_summary.get("currency") or "ZAR")

    story = []
    story.append(Paragraph("Quote Pack Summary", title_style))
    story.append(Paragraph(f"<b>Buyer:</b> {_clean(quote_pack_payload.get('buyer_name'))}", sub_style))
    story.append(Paragraph(f"<b>RFQ Number:</b> {_clean(quote_pack_payload.get('rfq_number'))}", sub_style))
    story.append(Paragraph(f"<b>Document Title:</b> {_clean(quote_pack_payload.get('document_title'))}", sub_style))
    story.append(Paragraph(f"<b>Quote Reference:</b> {_clean(quote_pack_payload.get('quote_reference'))}", sub_style))
    story.append(Spacer(1, 5 * mm))

    summary_rows = [
        ["Currency", _clean(quote_pack_summary.get("currency"))],
        ["Prices Include VAT", str(bool(quote_pack_summary.get("prices_include_vat", True)))],
        ["VAT Rate", f"{_coerce_float(quote_pack_summary.get('vat_rate')) or 0.0:.2f}%"],
        ["Subtotal", _fmt_money(quote_pack_summary.get("subtotal"), currency)],
        ["VAT Amount", _fmt_money(quote_pack_summary.get("vat_amount"), currency)],
        ["Grand Total", _fmt_money(quote_pack_summary.get("grand_total"), currency)],
        ["Priced Rows", str(int(quote_pack_summary.get("priced_rows") or 0))],
        ["Pending Rows", str(int(quote_pack_summary.get("pending_rows") or 0))],
        ["Review Rows Held Back", str(int(quote_pack_summary.get("review_rows_held_back") or 0))],
    ]
    summary_table = Table(summary_rows, colWidths=[58 * mm, 62 * mm], hAlign="LEFT")
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#D9E2F3")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9EB6D8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C5D1E3")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("<b>Rendered Buyer Pricing Schedule PDF</b>", body_style))
    story.append(Paragraph(_clean(rendered_buyer_pdf_path), body_style))
    story.append(Spacer(1, 4 * mm))

    items = _safe_list(quote_pack_payload.get("items"))
    preview_rows = [["Item", "Description", "Unit", "Qty", "Unit Price", "Line Total"]]
    for row in items[:12]:
        data = _safe_dict(row)
        preview_rows.append(
            [
                _clean(data.get("item_number")),
                _clean(data.get("description"))[:62],
                _clean(data.get("unit")),
                _clean(data.get("quantity")),
                _fmt_money(data.get("unit_price"), currency),
                _fmt_money(data.get("line_total"), currency),
            ]
        )

    preview_table = Table(
        preview_rows,
        colWidths=[12 * mm, 72 * mm, 16 * mm, 16 * mm, 24 * mm, 24 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    preview_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9EB6D8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2F3")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(Paragraph("<b>Item Preview (first 12 rows)</b>", body_style))
    story.append(Spacer(1, 2 * mm))
    story.append(preview_table)

    doc.build(story)


def build_quote_pack_output(
    record: Dict[str, Any],
) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    quote_pack_payload = _safe_dict(payload.get("quote_pack_payload"))
    quote_pack_summary = _safe_dict(payload.get("quote_pack_summary"))
    rendered_buyer_pdf_path = _clean(payload.get("rendered_buyer_pdf_path"))
    metadata = _safe_dict(payload.get("metadata"))

    rfq_number = _clean(
        quote_pack_payload.get("rfq_number")
        or metadata.get("buyer_rfq_number")
        or "RFQ"
    )
    safe_ref = _safe_ref_slug(rfq_number, max_len=80)
    output_dir = Path(_clean(metadata.get("pdf_output_dir") or str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "generated_quotes")))
    output_dir.mkdir(parents=True, exist_ok=True)
    quote_pack_pdf_path = output_dir / f"{safe_ref}_quote_pack_summary.pdf"

    _build_quote_pack_pdf(
        quote_pack_pdf_path,
        quote_pack_payload=quote_pack_payload,
        quote_pack_summary=quote_pack_summary,
        rendered_buyer_pdf_path=rendered_buyer_pdf_path,
    )

    items = _safe_list(quote_pack_payload.get("items"))
    pending_rows = int(quote_pack_summary.get("pending_rows") or 0)
    result = {
        "quote_pack_builder": {
            "input_rows": len(items),
            "output_rows": len(items),
            "pending_rows": pending_rows,
            "review_rows_held_back": int(quote_pack_summary.get("review_rows_held_back") or 0),
            "quote_pack_total": _coerce_float(quote_pack_summary.get("grand_total")) or 0.0,
            "quote_pack_pdf_path": str(quote_pack_pdf_path),
            "rendered_buyer_pdf_path": rendered_buyer_pdf_path,
        },
        "quote_pack_pdf_path": str(quote_pack_pdf_path),
        "quote_pack_ready_count": len(items),
        "quote_pack_pending_count": pending_rows,
    }
    return result


def attach_quote_pack_builder_to_record(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    payload.update(build_quote_pack_output(payload))
    return payload



