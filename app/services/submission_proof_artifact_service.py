from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
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


def _dedupe_strings(values: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        cleaned = _clean(value)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        output.append(cleaned)
    return output


def _build_receipt_pdf(pdf_path: Path, receipt: Dict[str, Any]) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ProofTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ProofBody",
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

    story = []
    story.append(Paragraph("Submission Proof Receipt", title_style))
    story.append(Spacer(1, 2 * mm))

    summary_rows = [
        ["RFQ Number", _clean(receipt.get("rfq_number"))],
        ["Buyer Name", _clean(receipt.get("buyer_name"))],
        ["Document Title", _clean(receipt.get("document_title"))],
        ["Quote Reference", _clean(receipt.get("quote_reference"))],
        ["Submission Email Ready", str(bool(receipt.get("submission_email_ready")))],
        ["Submission Email Sent", str(bool(receipt.get("submission_email_sent")))],
        ["Sent At UTC", _clean(receipt.get("submission_email_sent_at_utc"))],
        ["Recipient Count", str(int(receipt.get("recipient_count") or 0))],
        ["Attachment Count", str(int(receipt.get("attachment_count") or 0))],
        ["Review Rows Held Back", str(int(receipt.get("review_rows_held_back") or 0))],
    ]
    summary_table = Table(summary_rows, colWidths=[54 * mm, 100 * mm], hAlign="LEFT")
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

    story.append(Paragraph("<b>Recipients</b>", body_style))
    for item in _safe_list(receipt.get("used_recipients")):
        story.append(Paragraph(_clean(item), body_style))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("<b>Attachments</b>", body_style))
    for item in _safe_list(receipt.get("used_attachments")):
        story.append(Paragraph(_clean(item), body_style))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("<b>Send Result</b>", body_style))
    story.append(Paragraph(_clean(receipt.get("send_message")), body_style))

    doc.build(story)


def build_submission_proof_artifacts(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    metadata = _safe_dict(payload.get("metadata"))
    email_send_result = _safe_dict(payload.get("email_send_result"))

    rfq_number = _clean(
        payload.get("rfq_number")
        or payload.get("reference_number")
        or metadata.get("buyer_rfq_number")
        or "RFQ"
    )
    buyer_name = _clean(payload.get("buyer_name") or metadata.get("buyer_name"))
    document_title = _clean(payload.get("title") or metadata.get("title"))
    quote_reference = _clean(
        metadata.get("quote_reference")
        or payload.get("quote_reference")
        or rfq_number
    )

    output_dir = Path(_clean(metadata.get("pdf_output_dir") or "runtime/generated_quotes"))
    safe_ref = "".join(ch if ch.isalnum() else "_" for ch in rfq_number).strip("_") or "RFQ"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    proof_dir = output_dir / f"{safe_ref}_submission_proof"
    proof_dir.mkdir(parents=True, exist_ok=True)

    used_recipients = _dedupe_strings([str(x) for x in _safe_list(email_send_result.get("used_recipients"))])
    used_attachments = _dedupe_strings([str(x) for x in _safe_list(email_send_result.get("used_attachments"))])

    receipt = {
        "rfq_number": rfq_number,
        "buyer_name": buyer_name,
        "document_title": document_title,
        "quote_reference": quote_reference,
        "submission_email_ready": bool(payload.get("submission_email_ready")),
        "submission_email_sent": bool(payload.get("submission_email_sent")),
        "submission_email_sent_at_utc": _clean(payload.get("submission_email_sent_at_utc")),
        "send_attempted": bool(email_send_result.get("attempted")),
        "send_message": _clean(email_send_result.get("message")),
        "used_sender_email": _clean(email_send_result.get("used_sender_email")),
        "used_recipients": used_recipients,
        "used_attachments": used_attachments,
        "recipient_count": len(used_recipients),
        "attachment_count": len(used_attachments),
        "review_rows_held_back": len(_safe_list(payload.get("review_rows"))),
        "quote_pack_pdf_path": _clean(payload.get("quote_pack_pdf_path")),
        "rendered_buyer_pdf_path": _clean(payload.get("rendered_buyer_pdf_path")),
        "submission_pack_manifest_path": _clean(payload.get("submission_pack_manifest_path")),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    json_path = proof_dir / f"{safe_ref}_submission_receipt_{stamp}.json"
    txt_path = proof_dir / f"{safe_ref}_submission_receipt_{stamp}.txt"
    pdf_path = proof_dir / f"{safe_ref}_submission_receipt_{stamp}.pdf"

    json_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")

    txt_lines = [
        "Submission Proof Receipt",
        f"RFQ Number: {receipt['rfq_number']}",
        f"Buyer Name: {receipt['buyer_name']}",
        f"Document Title: {receipt['document_title']}",
        f"Quote Reference: {receipt['quote_reference']}",
        f"Submission Email Ready: {receipt['submission_email_ready']}",
        f"Submission Email Sent: {receipt['submission_email_sent']}",
        f"Submission Email Sent At UTC: {receipt['submission_email_sent_at_utc']}",
        f"Send Attempted: {receipt['send_attempted']}",
        f"Send Message: {receipt['send_message']}",
        f"Used Sender Email: {receipt['used_sender_email']}",
        f"Recipient Count: {receipt['recipient_count']}",
        f"Attachment Count: {receipt['attachment_count']}",
        f"Review Rows Held Back: {receipt['review_rows_held_back']}",
        "",
        "Recipients:",
    ]
    txt_lines.extend(f"- {x}" for x in used_recipients)
    txt_lines.append("")
    txt_lines.append("Attachments:")
    txt_lines.extend(f"- {x}" for x in used_attachments)
    txt_path.write_text("\n".join(txt_lines), encoding="utf-8")

    _build_receipt_pdf(pdf_path, receipt)

    return {
        "submission_proof_artifacts": {
            "proof_directory": str(proof_dir),
            "receipt_json_path": str(json_path),
            "receipt_txt_path": str(txt_path),
            "receipt_pdf_path": str(pdf_path),
            "submission_email_sent": bool(payload.get("submission_email_sent")),
            "send_attempted": bool(email_send_result.get("attempted")),
            "recipient_count": len(used_recipients),
            "attachment_count": len(used_attachments),
        },
        "submission_proof_directory": str(proof_dir),
        "submission_receipt_json_path": str(json_path),
        "submission_receipt_txt_path": str(txt_path),
        "submission_receipt_pdf_path": str(pdf_path),
    }


def attach_submission_proof_artifacts_to_record(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    payload.update(build_submission_proof_artifacts(payload))
    return payload


