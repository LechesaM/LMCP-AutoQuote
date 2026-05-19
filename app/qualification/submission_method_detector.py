from __future__ import annotations

import re
from typing import Any, Dict

from app.qualification.rfq_language_intelligence import analyze_rfq_language


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def detect_submission_method(rfq_record_or_dict: Dict[str, Any], *, language_intelligence: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(rfq_record_or_dict or {})
    language_intelligence = language_intelligence or analyze_rfq_language(payload)
    text = _normalize(
        " ".join(
            [
                str(payload.get("submission_instructions") or ""),
                str(payload.get("extracted_text") or ""),
                str(payload.get("source_text") or ""),
            ]
        )
    )
    target = ""
    method = "unknown"
    confidence = 0.35

    email_match = EMAIL_RE.search(text)
    url_match = URL_RE.search(text)
    language_flags = set(language_intelligence.get("risk_flags", []))

    if any(keyword in text for keyword in ("physical submission", "tender box", "dropbox", "drop box", "hand delivery", "courier")) or "physical_submission_requirement" in language_flags:
        method = "physical_delivery"
        confidence = 0.95
        target = payload.get("physical_address") or payload.get("delivery_address") or ""
    elif any(keyword in text for keyword in ("portal", "e-tender", "etender", "e submission", "electronic submission", "online submission", "e-submission")) or "e_submission_requirement" in language_flags:
        method = "portal"
        confidence = 0.9
        target = url_match.group(0) if url_match else str(payload.get("portal_url") or payload.get("portal") or "")
    elif email_match or any(keyword in text for keyword in ("email submission", "submit by email", "email to", "e-mail submission")) or "email_submission_requirement" in language_flags:
        method = "email"
        confidence = 0.96 if email_match else 0.88
        target = email_match.group(0) if email_match else str(payload.get("submission_email") or payload.get("email") or "")
    elif any(keyword in text for keyword in ("courier", "dropbox", "tender box", "hand delivery")):
        method = "courier_hand_delivery"
        confidence = 0.85
        target = payload.get("physical_address") or payload.get("delivery_address") or ""

    automation_candidate = method == "email"
    manual_handling_required = method != "email"
    return {
        "method": method,
        "confidence": confidence,
        "target": target,
        "automation_candidate": automation_candidate,
        "manual_handling_required": manual_handling_required,
        "language_evidence": language_intelligence.get("evidence_phrases", []),
    }
