from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import html
import json
import re
import shutil
import traceback
import zipfile

SERVICE_VERSION = "V45_PDF_RENDERER_SUBMISSION_PREP_V45_1_PROFESSIONAL_NOTES"
DEFAULT_OUTPUT_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "submission_pack_v45"
DEFAULT_COMPANY_NAME = "Lechesa Manaba Consulting and Projects (Pty) Ltd"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: Any, fallback: str = "RFQ") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _resolve_path(value: str | Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def _read_json_file(path_value: str | Path) -> Dict[str, Any]:
    path = _resolve_path(path_value)
    return json.loads(path.read_text(encoding="utf-8"))


def _find_v44_metadata(workspace: Path) -> Path:
    candidates = [
        workspace / "quote_pack_metadata_v44.json",
        workspace / "metadata.json",
    ]
    for c in candidates:
        if c.exists():
            return c

    matches = list(workspace.glob("*metadata*.json"))
    if matches:
        return matches[0]

    raise FileNotFoundError(f"No V44 metadata JSON found in {workspace}")


def _format_currency(value: Any) -> str:
    return f"R {_money(value):,.2f}"


def _professional_quotation_notes() -> List[str]:
    return [
        "This quotation is valid for 30 days from the date of issue, or up to 60 days if required by the buyer.",
        "Prices are quoted in South African Rand (ZAR) and include VAT where indicated.",
        "Supply and delivery will be carried out in accordance with the RFQ requirements, specifications, and delivery instructions issued by the buyer.",
        "This quotation is submitted together with the required supporting compliance documents.",
    ]


def _generate_pdf_with_reportlab(
    pdf_path: Path,
    metadata: Dict[str, Any],
    company_name: str,
) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
        )
    except Exception as exc:
        raise RuntimeError("ReportLab is required for V45 PDF rendering. Install with: pip install reportlab") from exc

    buyer_rfq = metadata.get("buyer_rfq_number") or "RFQ"
    quote_number = metadata.get("quote_number") or f"LMCP-QUOTE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    submission = metadata.get("submission") or {}
    totals = metadata.get("totals") or {}
    line_items = metadata.get("line_items") or []

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Small",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    ))
    styles.add(ParagraphStyle(
        name="Cell",
        parent=styles["Normal"],
        fontSize=7,
        leading=8,
    ))

    story = []
    story.append(Paragraph("FORMAL QUOTATION", styles["Title"]))
    story.append(Paragraph(html.escape(company_name), styles["Heading2"]))
    story.append(Paragraph(f"<b>Quote Number:</b> {html.escape(str(quote_number))}", styles["Normal"]))
    story.append(Paragraph(f"<b>Buyer RFQ:</b> {html.escape(str(buyer_rfq))}", styles["Normal"]))
    story.append(Paragraph(f"<b>Prepared:</b> {_now_iso()}", styles["Normal"]))
    story.append(Paragraph(f"<b>Submission Email:</b> {html.escape(str(submission.get('submission_email') or 'Not detected'))}", styles["Normal"]))
    story.append(Spacer(1, 8))

    data = [[
        "#",
        "Description",
        "Qty",
        "Unit",
        "Unit Price Excl VAT",
        "Total Excl VAT",
        "VAT",
        "Total Incl VAT",
    ]]

    for item in line_items:
        data.append([
            str(item.get("item_no") or ""),
            Paragraph(html.escape(str(item.get("description") or "")), styles["Cell"]),
            str(item.get("quantity") or ""),
            str(item.get("unit") or "each"),
            _format_currency(item.get("unit_price_excl_vat")),
            _format_currency(item.get("total_excl_vat")),
            _format_currency(item.get("vat_amount")),
            _format_currency(item.get("total_incl_vat")),
        ])

    table = Table(
        data,
        colWidths=[10 * mm, 58 * mm, 14 * mm, 15 * mm, 26 * mm, 25 * mm, 20 * mm, 25 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))

    totals_data = [
        ["Total Excl VAT", _format_currency(totals.get("total_excl_vat"))],
        ["VAT", _format_currency(totals.get("total_vat"))],
        ["Total Incl VAT", _format_currency(totals.get("total_incl_vat"))],
    ]
    totals_table = Table(totals_data, colWidths=[45 * mm, 45 * mm], hAlign="RIGHT")
    totals_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, 2), (-1, 2), colors.lightgrey),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Notes", styles["Heading3"]))
    for note in _professional_quotation_notes():
        story.append(Paragraph(f"• {html.escape(note)}", styles["Small"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Generated by LMCP AutoQuote {SERVICE_VERSION}.", styles["Small"]))

    doc.build(story)


def _copy_if_exists(src_value: str | Path, dest_dir: Path) -> Optional[str]:
    src = _resolve_path(src_value)
    if not src.exists():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    return str(dest)


def _collect_attachments(metadata: Dict[str, Any], bundle_dir: Path, quote_pdf_path: Path) -> List[Dict[str, Any]]:
    attachments_dir = bundle_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    attachments: List[Dict[str, Any]] = []

    pdf_dest = attachments_dir / quote_pdf_path.name
    shutil.copy2(quote_pdf_path, pdf_dest)
    attachments.append({"type": "quotation_pdf", "path": str(pdf_dest), "status": "included"})

    artifacts = metadata.get("artifacts") or {}

    for key in ["pricing_csv", "quote_engine_payload_json"]:
        value = artifacts.get(key)
        if value:
            copied = _copy_if_exists(value, attachments_dir)
            attachments.append({
                "type": key,
                "path": copied,
                "source": value,
                "status": "included" if copied else "missing",
            })

    compliance_dir_value = artifacts.get("compliance_dir")
    if compliance_dir_value:
        compliance_dir = _resolve_path(compliance_dir_value)
        if compliance_dir.exists():
            for f in sorted(compliance_dir.glob("*")):
                if f.is_file():
                    copied = _copy_if_exists(f, attachments_dir / "compliance")
                    attachments.append({
                        "type": "compliance",
                        "path": copied,
                        "source": str(f),
                        "status": "included" if copied else "missing",
                    })

    return attachments


def _make_email_draft(metadata: Dict[str, Any], attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    buyer_rfq = metadata.get("buyer_rfq_number") or "RFQ"
    quote_number = metadata.get("quote_number") or "LMCP-QUOTE"
    submission = metadata.get("submission") or {}
    submission_email = submission.get("submission_email")

    subject = f"Quotation Submission - {buyer_rfq} - {quote_number}"
    body = (
        "Dear Bids Team,\n\n"
        f"Please find attached the quotation submission for {buyer_rfq}.\n\n"
        "Attached documents include the formal quotation, pricing schedule, and available compliance documents.\n\n"
        "Kind regards,\n"
        "Lechesa Manaba\n"
        "Lechesa Manaba Consulting and Projects (Pty) Ltd\n"
    )

    return {
        "to": submission_email,
        "subject": subject,
        "body": body,
        "attachments": [
            a.get("path")
            for a in attachments
            if a.get("status") == "included"
            and a.get("path")
            and not str(a.get("path")).lower().endswith(".zip")
        ],
        "ready_to_send": bool(submission_email),
        "manual_review_required": True,
        "zip_allowed_for_submission": False,
    }


def prepare_submission_from_v44_workspace(
    workspace_path: str,
    output_dir: Optional[str] = None,
    company_name: str = DEFAULT_COMPANY_NAME,
    create_zip: bool = True,
) -> Dict[str, Any]:
    started_at = _now_iso()

    try:
        workspace = _resolve_path(workspace_path)
        if not workspace.exists():
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V44 workspace not found.",
                "workspace_path": str(workspace),
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        metadata_path = _find_v44_metadata(workspace)
        metadata = _read_json_file(metadata_path)

        buyer_rfq = metadata.get("buyer_rfq_number") or workspace.name
        quote_number = metadata.get("quote_number") or f"LMCP-QUOTE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        safe_rfq = _safe_name(buyer_rfq)
        safe_quote = _safe_name(quote_number)

        out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        if not out_root.is_absolute():
            out_root = Path.cwd() / out_root
        bundle_dir = out_root / f"{safe_rfq}__{safe_quote}"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        quote_pdf_path = bundle_dir / "formal_quotation_v45.pdf"
        _generate_pdf_with_reportlab(quote_pdf_path, metadata, company_name=company_name)

        attachments = _collect_attachments(metadata, bundle_dir, quote_pdf_path)
        email_draft = _make_email_draft(metadata, attachments)

        manifest = {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "message": "V45 PDF and submission pack prepared.",
            "buyer_rfq_number": buyer_rfq,
            "quote_number": quote_number,
            "source_v44_workspace": str(workspace),
            "source_v44_metadata": str(metadata_path),
            "workspace": str(bundle_dir),
            "started_at": started_at,
            "completed_at": _now_iso(),
            "artifacts": {
                "quote_pdf": str(quote_pdf_path),
                "email_draft_json": str(bundle_dir / "email_draft_v45.json"),
                "submission_manifest_json": str(bundle_dir / "submission_manifest_v45.json"),
                "attachments_dir": str(bundle_dir / "attachments"),
            },
            "submission": {
                "submission_email": email_draft.get("to"),
                "ready_to_send": email_draft.get("ready_to_send"),
                "manual_review_required": True,
                "must_handwrite_forms": (metadata.get("submission") or {}).get("must_handwrite_forms"),
                "zip_allowed_for_submission": False,
            },
            "attachments": attachments,
            "email_draft": email_draft,
            "quotation_notes": _professional_quotation_notes(),
        }

        email_draft_path = bundle_dir / "email_draft_v45.json"
        manifest_path = bundle_dir / "submission_manifest_v45.json"
        email_draft_path.write_text(json.dumps(email_draft, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        if create_zip:
            zip_path = bundle_dir.with_suffix(".zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                for f in bundle_dir.rglob("*"):
                    if f.is_file():
                        z.write(f, f.relative_to(bundle_dir))
            manifest["artifacts"]["zip_bundle"] = str(zip_path)
            manifest["submission"]["zip_allowed_for_submission"] = False
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        return manifest

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V45 submission preparation failed.",
            "workspace_path": workspace_path,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def prepare_submission_from_v44_json(
    v44_metadata_json: str,
    output_dir: Optional[str] = None,
    company_name: str = DEFAULT_COMPANY_NAME,
    create_zip: bool = True,
) -> Dict[str, Any]:
    metadata_path = _resolve_path(v44_metadata_json)
    if not metadata_path.exists():
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V44 metadata JSON not found.",
            "v44_metadata_json": str(metadata_path),
            "started_at": _now_iso(),
            "completed_at": _now_iso(),
        }

    metadata = _read_json_file(metadata_path)
    workspace = metadata.get("workspace")
    if not workspace:
        workspace = str(metadata_path.parent)

    return prepare_submission_from_v44_workspace(
        workspace_path=workspace,
        output_dir=output_dir,
        company_name=company_name,
        create_zip=create_zip,
    )


def prepare_submission_from_pdf(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    output_dir: Optional[str] = None,
    company_name: str = DEFAULT_COMPANY_NAME,
    margin_percent: float = 25.0,
    minimum_profit_required: float = 30000.0,
    apply_profit_floor: bool = True,
    min_confidence: float = 0.35,
    create_zip: bool = True,
) -> Dict[str, Any]:
    started_at = _now_iso()

    try:
        from app.services.quote_pack_v44_service import generate_quote_pack_from_pdf

        v44_result = generate_quote_pack_from_pdf(
            input_pdf=input_pdf,
            buyer_rfq_number=buyer_rfq_number,
            company_name=company_name,
            output_dir=None,
            margin_percent=margin_percent,
            minimum_profit_required=minimum_profit_required,
            apply_profit_floor=apply_profit_floor,
            min_confidence=min_confidence,
        )

        if v44_result.get("status") != "ok":
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V44 quote pack failed, so V45 could not continue.",
                "v44_result": v44_result,
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        result = prepare_submission_from_v44_workspace(
            workspace_path=v44_result.get("workspace"),
            output_dir=output_dir,
            company_name=company_name,
            create_zip=create_zip,
        )
        result["v44_workspace"] = v44_result.get("workspace")
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V45 full PDF workflow failed.",
            "input_pdf": input_pdf,
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v45_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V45.1 PDF Renderer and Submission Prep",
        "description": "Renders V44 quote metadata into a formal PDF with professional quotation notes, prepares email draft JSON, copies attachments, excludes ZIP files from buyer email attachments, and builds a zip archive only for internal storage.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "quotation_notes": _professional_quotation_notes(),
        "submission_policy": {
            "zip_allowed_for_submission": False,
            "zip_created_for_internal_archive_only": True,
        },
        "endpoints": {
            "status": "/v45-submission-pack/status",
            "prepare_from_v44_workspace": "/v45-submission-pack/prepare-from-v44-workspace",
            "prepare_from_v44_json": "/v45-submission-pack/prepare-from-v44-json",
            "prepare_from_pdf": "/v45-submission-pack/prepare-from-pdf",
        },
        "ready": True,
    }
