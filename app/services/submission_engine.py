from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path
from datetime import datetime
from app.services.email_submission_service import EmailSubmissionService


SUBMISSION_LOG_FILE = os.getenv(
    "LMCP_SUBMISSION_LOG_FILE",
    "runtime/submission_log.json"
)


def _ensure_runtime_dir() -> None:
    os.makedirs(os.path.dirname(SUBMISSION_LOG_FILE), exist_ok=True)


def _read_log() -> list:
    _ensure_runtime_dir()
    if not os.path.exists(SUBMISSION_LOG_FILE):
        with open(SUBMISSION_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

    with open(SUBMISSION_LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_log(entries: list) -> None:
    _ensure_runtime_dir()
    with open(SUBMISSION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_rejected_pack(
    rfq: Dict[str, Any],
    reason: str,
    score_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": True,
        "rfq_id": rfq.get("rfq_id"),
        "title": rfq.get("title"),
        "ready": False,
        "reason": reason,
        "recommended_action": (score_result or {}).get("recommended_action", "SKIP"),
        "score": (score_result or {}).get("score", 0.0),
        "priority": (score_result or {}).get("priority", "LOW"),
    }

def _build_rejected_pack(
    rfq: Dict[str, Any],
    reason: str,
    score_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        ...
    }


def _write_submission_pack_text(
    rfq: Dict[str, Any],
    classification: Dict[str, Any],
    quote: Dict[str, Any],
    pack: Dict[str, Any],
) -> str:
    base_dir = Path(__file__).resolve().parents[2]
    output_dir = base_dir / "generated_submission_packs"
    output_dir.mkdir(parents=True, exist_ok=True)

    rfq_id = str(rfq.get("rfq_id") or "general")
    file_path = output_dir / f"{rfq_id}_submission_pack.txt"

    selected_supplier = quote.get("selected_supplier") or {}

    content = f"""LMCP AUTOQUOTE SUBMISSION PACK
================================

RFQ TITLE: {rfq.get("title")}
RFQ ID: {rfq.get("rfq_id")}
CATEGORY: {classification.get("category")}
SUBMISSION METHOD: {pack.get("submission_method")}
DEADLINE: {pack.get("deadline")}

PRICING SUMMARY
--------------------------------
Quote Total Excl VAT: R{pack.get("quote_total_excl_vat")}
Quote Total Incl VAT: R{pack.get("quote_total_incl_vat")}
Gross Profit: R{pack.get("gross_profit")}

SUPPLIER
--------------------------------
Supplier: {selected_supplier.get("supplier_name")}
Province: {selected_supplier.get("province")}
City: {selected_supplier.get("city")}
Contact: {selected_supplier.get("contact_person")}
Email: {selected_supplier.get("email")}
Phone: {selected_supplier.get("phone")}

DOCUMENTS
--------------------------------
- Cover Letter
- Quotation / Pricing Schedule
- CSD Registration Report
- Tax Compliance Status PIN
- SBD Documents
- Identity Document

SYSTEM GENERATED
--------------------------------
Generated At: {datetime.now().isoformat()}
"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(file_path)


def build_submission_pack(
    rfq: Dict[str, Any],
    classification: Dict[str, Any],
    quote: Dict[str, Any],
    score_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    excluded_category = classification.get("excluded_category")
    is_construction = bool(classification.get("is_construction", False))
    supply_only = bool(classification.get("supply_only", False))
    has_compulsory_briefing = bool(classification.get("has_compulsory_briefing", False))
    eligible = bool(classification.get("eligible", False))

    if excluded_category:
        return _build_rejected_pack(
            rfq,
            f"Submission pack not prepared because RFQ is in excluded category '{excluded_category}'.",
            score_result,
        )

    if is_construction:
        return _build_rejected_pack(
            rfq,
            "Submission pack not prepared because RFQ includes construction / works / installation / maintenance scope.",
            score_result,
        )

    if not supply_only:
        return _build_rejected_pack(
            rfq,
            "Submission pack not prepared because RFQ is not classified as pure supply-and-delivery.",
            score_result,
        )

    if has_compulsory_briefing:
        return _build_rejected_pack(
            rfq,
            "Submission pack not prepared because RFQ includes a compulsory or mandatory briefing/site meeting.",
            score_result,
        )

    if not eligible:
        return _build_rejected_pack(
            rfq,
            "Submission pack not prepared because RFQ did not pass supply eligibility rules.",
            score_result,
        )

    if not quote.get("can_quote"):
        return _build_rejected_pack(
            rfq,
            f"Cannot build submission pack because pricing route is unavailable. {quote.get('rejection_reason', '')}".strip(),
            score_result,
        )

    if not quote.get("profit_floor_passed", False):
        return _build_rejected_pack(
            rfq,
            f"Submission pack not prepared because profit floor failed. {quote.get('rejection_reason', '')}".strip(),
            score_result,
        )

    if score_result.get("recommended_action") != "SUBMIT":
        return _build_rejected_pack(
            rfq,
            "Submission pack not prepared because RFQ is not approved for submission.",
            score_result,
        )


    submission_method = classification.get("submission_mode", "unknown")
    deadline = rfq.get("deadline")

    documents = [
        "Cover Letter",
        "Quotation / Pricing Schedule",
        "CSD Registration Report",
        "Tax Compliance Status PIN",
        "SBD Documents",
        "Identity Document",
    ]

    pack = {
        "rfq_id": rfq.get("rfq_id"),
        "title": rfq.get("title"),
        "ready": True,
        "submission_method": submission_method,
        "deadline": deadline,
        "delivery_location": classification.get("delivery_location"),
        "category": classification.get("category"),
        "score": score_result.get("score"),
        "priority": score_result.get("priority"),
        "recommended_action": score_result.get("recommended_action"),
        "selected_supplier": quote.get("selected_supplier"),
        "quote_total_excl_vat": quote.get("cost_breakdown", {}).get("quote_total_excl_vat"),
        "quote_total_incl_vat": quote.get("cost_breakdown", {}).get("quote_total_incl_vat"),
        "gross_profit": quote.get("cost_breakdown", {}).get("gross_profit"),
        "documents": documents,
        "email_to": rfq.get("submission_email"),
        "portal_url": rfq.get("portal_url"),
    }

    pack["generated_pack_path"] = _write_submission_pack_text(
        rfq=rfq,
        classification=classification,
        quote=quote,
        pack=pack,
    )

    return pack


def mark_submission_status(
    rfq_id: str,
    status: str,
    submitted_by: str = "system",
    notes: Optional[str] = None,
    category: Optional[str] = None,
    gross_profit: Optional[float] = None,
    award_value_excl_vat: Optional[float] = None,
) -> Dict[str, Any]:
    entries = _read_log()

    record = {
        "rfq_id": rfq_id,
        "status": status,
        "submitted_by": submitted_by,
        "notes": notes or "",
        "category": category or "",
        "gross_profit": float(gross_profit or 0.0),
        "award_value_excl_vat": float(award_value_excl_vat or 0.0),
        "timestamp_utc": _utc_now_iso(),
    }
    entries.append(record)
    _write_log(entries)
    return record


def get_submission_summary() -> Dict[str, Any]:
    entries = _read_log()

    total = len(entries)
    sent = sum(1 for e in entries if e["status"].lower() == "submitted")
    failed = sum(1 for e in entries if e["status"].lower() == "failed")
    pending = sum(1 for e in entries if e["status"].lower() == "pending")
    reviewed = sum(1 for e in entries if e["status"].lower() == "reviewed")
    won = sum(1 for e in entries if e["status"].lower() == "won")

    total_profit = round(
        sum(float(e.get("gross_profit", 0.0)) for e in entries if e["status"].lower() == "won"),
        2,
    )
    total_award_value = round(
        sum(float(e.get("award_value_excl_vat", 0.0)) for e in entries if e["status"].lower() == "won"),
        2,
    )

    category_profit_map: Dict[str, float] = {}
    for entry in entries:
        if entry["status"].lower() != "won":
            continue
        category = entry.get("category") or "uncategorized"
        category_profit_map[category] = category_profit_map.get(category, 0.0) + float(
            entry.get("gross_profit", 0.0)
        )

    category_profit_leaderboard = [
        {"category": category, "profit": round(profit, 2)}
        for category, profit in sorted(category_profit_map.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "total_records": total,
        "submitted": sent,
        "failed": failed,
        "pending": pending,
        "reviewed": reviewed,
        "won": won,
        "total_profit_from_wins": total_profit,
        "total_award_value_from_wins": total_award_value,
        "category_profit_leaderboard": category_profit_leaderboard,
        "latest": entries[-20:],
    }

class SubmissionEngine:

    DEFAULT_TO_EMAIL = "tenders@municipality.gov.za"

    @classmethod
    def send_email_with_pdf(cls, quote: dict, pdf_path: str) -> dict:
        import smtplib
        from email.message import EmailMessage
        from pathlib import Path

        try:
            to_email = (
                quote.get("submission_email")
                or quote.get("rfq_snapshot", {}).get("submission_email")
            )

            if not to_email:
                return {
                    "success": False,
                    "error": "No submission email found in RFQ",
                }

            subject = f"Quotation Submission: {quote.get('title')}"

            body = f"""
Dear Sir/Madam,

Please find attached our quotation for:

{quote.get('title')}

Kind regards,

Lechesa Manaba Consulting and Projects (Pty) Ltd
"""

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = "lechesam@me.com"
            msg["To"] = to_email
            msg.set_content(body)

            with open(pdf_path, "rb") as f:
                msg.add_attachment(
                    f.read(),
                    maintype="application",
                    subtype="pdf",
                    filename=Path(pdf_path).name,
                )

            with smtplib.SMTP("smtp.mail.me.com", 587) as smtp:
                smtp.starttls()
                smtp.login("lechesam@me.com", "xqlv-qwnk-vcsq-ibea")
                smtp.send_message(msg)

            return {
                "success": True,
                "sent_to": to_email,
                "pdf": pdf_path,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
