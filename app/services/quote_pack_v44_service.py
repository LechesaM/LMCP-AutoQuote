from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import csv
import html
import json
import re
import shutil
import traceback

LEGACY_SERVICE = True
SERVICE_VERSION = "V44_QUOTE_PACK_GENERATOR"
DEFAULT_OUTPUT_DIR = Path("runtime/quote_pack_v44")
DEFAULT_COMPANY_NAME = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
DEFAULT_CURRENCY = "ZAR"

DEFAULT_COMPLIANCE_FILES = [
    "runtime/compliance/Tax_Compliance_Pin.pdf",
    "runtime/compliance/CSD_Report.pdf",
    "runtime/compliance/BBBEE_Certificate.pdf",
    "runtime/compliance/LMCP_Company_Reg Certificate.pdf",
    "runtime/compliance/ID_LM Manaba.pdf",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: Any, fallback: str = "RFQ") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def _read_json(path_value: str) -> Dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _extract_v43_line_items(v43_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    line_items = v43_payload.get("line_items") or []

    normalized = []
    for idx, item in enumerate(line_items, start=1):
        normalized.append({
            "item_no": item.get("item_no") or idx,
            "description": item.get("description") or "",
            "original_description": item.get("original_description") or "",
            "quantity": _money(item.get("quantity")),
            "unit": item.get("unit") or "each",
            "unit_price_excl_vat": _money(item.get("unit_price_excl_vat")),
            "total_excl_vat": _money(item.get("total_excl_vat")),
            "vat_amount": _money(item.get("vat_amount")),
            "total_incl_vat": _money(item.get("total_incl_vat")),
            "currency": item.get("currency") or DEFAULT_CURRENCY,
            "pricing_method": item.get("pricing_method") or "",
            "confidence": item.get("confidence"),
            "source_page": item.get("source_page"),
        })
    return normalized


def _build_totals(line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_excl = _money(sum(_money(i.get("total_excl_vat")) for i in line_items))
    total_vat = _money(sum(_money(i.get("vat_amount")) for i in line_items))
    total_incl = _money(sum(_money(i.get("total_incl_vat")) for i in line_items))
    return {
        "currency": DEFAULT_CURRENCY,
        "total_excl_vat": total_excl,
        "total_vat": total_vat,
        "total_incl_vat": total_incl,
        "line_items_count": len(line_items),
    }


def _write_pricing_csv(path: Path, line_items: List[Dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "item_no",
                "description",
                "quantity",
                "unit",
                "unit_price_excl_vat",
                "total_excl_vat",
                "vat_amount",
                "total_incl_vat",
                "currency",
            ],
        )
        writer.writeheader()
        for item in line_items:
            writer.writerow({
                "item_no": item["item_no"],
                "description": item["description"],
                "quantity": item["quantity"],
                "unit": item["unit"],
                "unit_price_excl_vat": item["unit_price_excl_vat"],
                "total_excl_vat": item["total_excl_vat"],
                "vat_amount": item["vat_amount"],
                "total_incl_vat": item["total_incl_vat"],
                "currency": item["currency"],
            })


def _write_quote_html(
    path: Path,
    buyer_rfq_number: str,
    quote_number: str,
    company_name: str,
    line_items: List[Dict[str, Any]],
    totals: Dict[str, Any],
    submission_email: Optional[str],
    source_pdf: Optional[str],
) -> None:
    rows = []
    for item in line_items:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item['item_no']))}</td>"
            f"<td>{html.escape(str(item['description']))}</td>"
            f"<td>{item['quantity']}</td>"
            f"<td>{html.escape(str(item['unit']))}</td>"
            f"<td>R {item['unit_price_excl_vat']:,.2f}</td>"
            f"<td>R {item['total_excl_vat']:,.2f}</td>"
            f"<td>R {item['vat_amount']:,.2f}</td>"
            f"<td>R {item['total_incl_vat']:,.2f}</td>"
            "</tr>"
        )

    content = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(quote_number)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 36px; color: #111; }}
    .header {{ border-bottom: 3px solid #111; padding-bottom: 14px; margin-bottom: 24px; }}
    h1 {{ margin: 0; font-size: 26px; }}
    .muted {{ color: #555; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; font-size: 12px; vertical-align: top; }}
    th {{ background: #f2f2f2; text-align: left; }}
    .totals {{ margin-top: 20px; width: 360px; float: right; }}
    .totals td {{ font-weight: bold; }}
    .note {{ clear: both; padding-top: 30px; font-size: 12px; color: #333; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Formal Quotation</h1>
    <p><strong>{html.escape(company_name)}</strong></p>
    <p class="muted">Quote Number: {html.escape(quote_number)} | Buyer RFQ: {html.escape(buyer_rfq_number)}</p>
    <p class="muted">Prepared: {html.escape(_now_iso())}</p>
  </div>

  <p><strong>Submission Email:</strong> {html.escape(submission_email or "Not detected")}</p>
  <p><strong>Source PDF:</strong> {html.escape(source_pdf or "Not provided")}</p>

  <table>
    <thead>
      <tr>
        <th>#</th><th>Description</th><th>Qty</th><th>Unit</th>
        <th>Unit Price Excl VAT</th><th>Total Excl VAT</th><th>VAT</th><th>Total Incl VAT</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>

  <table class="totals">
    <tr><td>Total Excl VAT</td><td>R {totals['total_excl_vat']:,.2f}</td></tr>
    <tr><td>VAT</td><td>R {totals['total_vat']:,.2f}</td></tr>
    <tr><td>Total Incl VAT</td><td>R {totals['total_incl_vat']:,.2f}</td></tr>
  </table>

  <div class="note">
    <p>This quotation is prepared for the referenced RFQ and is subject to final director review before submission.</p>
    <p>Generated by LMCP AutoQuote {html.escape(SERVICE_VERSION)}.</p>
  </div>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def _copy_compliance_files(workspace: Path, compliance_files: Optional[List[str]]) -> List[Dict[str, Any]]:
    files = compliance_files or DEFAULT_COMPLIANCE_FILES
    out_dir = workspace / "compliance"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    missing = []
    for item in files:
        src = _resolve_path(item)
        if not src.exists():
            missing.append({"source": str(src), "status": "missing"})
            continue
        dest = out_dir / src.name
        try:
            shutil.copy2(src, dest)
            copied.append({"source": str(src), "copied_to": str(dest), "status": "copied"})
        except Exception as exc:
            missing.append({"source": str(src), "status": "copy_failed", "error": str(exc)})

    return copied + missing


def generate_quote_pack_from_v43_payload(
    v43_payload: Dict[str, Any],
    buyer_rfq_number: Optional[str] = None,
    company_name: str = DEFAULT_COMPANY_NAME,
    output_dir: Optional[str] = None,
    compliance_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    started_at = _now_iso()

    rfq = buyer_rfq_number or v43_payload.get("buyer_rfq_number") or "RFQ"
    safe_rfq = _safe_name(rfq)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    quote_number = f"LMCP-QUOTE-{timestamp}"

    out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not out_root.is_absolute():
        out_root = Path.cwd() / out_root

    workspace = out_root / f"{safe_rfq}__{quote_number}"
    workspace.mkdir(parents=True, exist_ok=True)

    line_items = _extract_v43_line_items(v43_payload)
    totals = _build_totals(line_items)

    if not line_items:
        return {
            "status": "needs_manual_review",
            "service_version": SERVICE_VERSION,
            "message": "No V43 line items found. Quote pack not generated.",
            "buyer_rfq_number": rfq,
            "started_at": started_at,
            "completed_at": _now_iso(),
        }

    submission_email = None
    v41_summary = v43_payload.get("v41_result_summary") or {}
    if isinstance(v41_summary, dict):
        submission_email = v41_summary.get("primary_submission_email")

    pricing_csv = workspace / "buyer_pricing_schedule_v44.csv"
    quote_html = workspace / "formal_quotation_v44.html"
    metadata_json = workspace / "quote_pack_metadata_v44.json"
    quote_engine_payload_json = workspace / "quote_engine_payload_v44.json"
    submission_manifest_json = workspace / "submission_manifest_v44.json"

    _write_pricing_csv(pricing_csv, line_items)
    _write_quote_html(
        quote_html,
        buyer_rfq_number=rfq,
        quote_number=quote_number,
        company_name=company_name,
        line_items=line_items,
        totals=totals,
        submission_email=submission_email,
        source_pdf=v43_payload.get("input_pdf"),
    )

    compliance_status = _copy_compliance_files(workspace, compliance_files)

    quote_engine_payload = v43_payload.get("quote_engine_payload") or {
        "buyer_rfq_number": rfq,
        "currency": DEFAULT_CURRENCY,
        "line_items": line_items,
    }

    quote_engine_payload["quote_number"] = quote_number
    quote_engine_payload["quote_pack_workspace"] = str(workspace)

    metadata = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "message": "Quote pack generated.",
        "buyer_rfq_number": rfq,
        "quote_number": quote_number,
        "company_name": company_name,
        "input_pdf": v43_payload.get("input_pdf"),
        "started_at": started_at,
        "completed_at": _now_iso(),
        "workspace": str(workspace),
        "artifacts": {
            "pricing_csv": str(pricing_csv),
            "quote_html": str(quote_html),
            "metadata_json": str(metadata_json),
            "quote_engine_payload_json": str(quote_engine_payload_json),
            "submission_manifest_json": str(submission_manifest_json),
            "compliance_dir": str(workspace / "compliance"),
        },
        "submission": {
            "submission_email": submission_email,
            "submission_ready": bool(submission_email),
            "requires_director_review": True,
            "must_handwrite_forms": v41_summary.get("must_handwrite_forms") if isinstance(v41_summary, dict) else None,
        },
        "totals": totals,
        "line_items": line_items,
        "source_v43_summary": v43_payload.get("pricing_summary") or {},
        "compliance_status": compliance_status,
    }

    submission_manifest = {
        "buyer_rfq_number": rfq,
        "quote_number": quote_number,
        "submission_email": submission_email,
        "submission_ready": bool(submission_email),
        "attachments": [
            str(quote_html),
            str(pricing_csv),
            *[row["copied_to"] for row in compliance_status if row.get("status") == "copied"],
        ],
        "manual_review_required": True,
        "notes": [
            "HTML quotation generated. Convert/print to PDF in next PDF-rendering layer if required.",
            "CSV buyer pricing schedule generated.",
            "Compliance files copied where available.",
        ],
    }

    quote_engine_payload_json.write_text(json.dumps(quote_engine_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    submission_manifest_json.write_text(json.dumps(submission_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    metadata_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    return metadata


def generate_quote_pack_from_v43_json(
    v43_json_path: str,
    buyer_rfq_number: Optional[str] = None,
    company_name: str = DEFAULT_COMPANY_NAME,
    output_dir: Optional[str] = None,
    compliance_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    started_at = _now_iso()
    path = _resolve_path(v43_json_path)

    if not path.exists():
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V43 JSON file not found.",
            "v43_json_path": str(path),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = generate_quote_pack_from_v43_payload(
            v43_payload=payload,
            buyer_rfq_number=buyer_rfq_number,
            company_name=company_name,
            output_dir=output_dir,
            compliance_files=compliance_files,
        )
        result["v43_json_path"] = str(path)
        return result
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Quote pack generation from V43 JSON failed.",
            "v43_json_path": str(path),
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def generate_quote_pack_from_pdf(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    company_name: str = DEFAULT_COMPANY_NAME,
    output_dir: Optional[str] = None,
    margin_percent: float = 25.0,
    minimum_profit_required: float = 30000.0,
    apply_profit_floor: bool = True,
    min_confidence: float = 0.35,
    compliance_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    started_at = _now_iso()
    try:
        from app.services.auto_pricing_v43_service import auto_price_pdf_with_v42

        v43_result = auto_price_pdf_with_v42(
            input_pdf=input_pdf,
            buyer_rfq_number=buyer_rfq_number,
            margin_percent=margin_percent,
            minimum_profit_required=minimum_profit_required,
            apply_profit_floor=apply_profit_floor,
            min_confidence=min_confidence,
        )

        if v43_result.get("status") != "ok":
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V43 auto-pricing failed, so V44 quote pack could not continue.",
                "v43_result": v43_result,
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        result = generate_quote_pack_from_v43_payload(
            v43_payload=v43_result,
            buyer_rfq_number=buyer_rfq_number,
            company_name=company_name,
            output_dir=output_dir,
            compliance_files=compliance_files,
        )
        result["v43_output_json"] = v43_result.get("output_json")
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V44 PDF quote pack workflow failed.",
            "input_pdf": input_pdf,
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_quote_pack_v44_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V44 Quote Pack Generator",
        "description": "Generates a submission-ready quote pack workspace from V43 pricing output, including quotation HTML, pricing CSV, quote payload, manifest, and compliance file collection.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "endpoints": {
            "status": "/v44-quote-pack/status",
            "generate_from_pdf": "/v44-quote-pack/generate-from-pdf",
            "generate_from_v43_json": "/v44-quote-pack/generate-from-v43-json",
        },
        "ready": True,
    }
