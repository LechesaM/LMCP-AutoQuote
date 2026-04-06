from __future__ import annotations

import re
from typing import Any, Dict, List


EMAIL_REGEX = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

EMAIL_SUBMISSION_PHRASES = [
    "submit via email",
    "submit by email",
    "submitted by email",
    "submission via email",
    "submission by email",
    "email submission",
    "e-mail submission",
    "submit quotations by email",
    "submit quotation by email",
    "quotation must be emailed",
    "quotations must be emailed",
    "rfq responses must be emailed",
    "send quotation to",
    "send quotations to",
    "email your quotation to",
    "email quotation to",
    "email quotations to",
    "forward your quotation to",
    "submit bid by email",
    "submit proposal by email",
    "proposals must be emailed",
    "bids must be emailed",
    "documents must be emailed",
    "send proposals to",
    "send bids to",
    "emailed to",
    "e-mailed to",
    "responses via email",
    "quotations should be emailed",
    "quotation should be emailed",
    "email address for submission",
    "submit tender documents by email",
]

NON_EMAIL_ONLY_PHRASES = [
    "hand delivery only",
    "submit at the tender box",
    "tender box",
    "physical submission only",
    "portal submission only",
    "must be uploaded on the portal",
    "upload on the portal",
    "courier to",
    "delivered to the tender box",
]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def collect_text(opportunity: Any) -> str:
    parts = [
        getattr(opportunity, "title", ""),
        getattr(opportunity, "description", ""),
        getattr(opportunity, "buyer_name", ""),
        getattr(opportunity, "category", ""),
        getattr(opportunity, "reference_no", ""),
        getattr(opportunity, "source_url", ""),
    ]
    return " | ".join(str(p) for p in parts if p)


def extract_emails(text: str) -> List[str]:
    emails = EMAIL_REGEX.findall(text or "")
    unique: List[str] = []
    seen = set()

    for e in emails:
        email = e.strip().lower().rstrip(".,;:")
        if email not in seen:
            seen.add(email)
            unique.append(email)

    return unique


def detect_email_submission(opportunity: Any) -> Dict[str, Any]:
    raw_text = collect_text(opportunity)
    text = normalize_text(raw_text)

    found_emails = extract_emails(raw_text)

    reasons: List[str] = []
    confidence = 0

    for phrase in EMAIL_SUBMISSION_PHRASES:
        if phrase in text:
            confidence += 20
            reasons.append(f"email submission phrase: {phrase}")

    if found_emails:
        confidence += min(30, 10 * len(found_emails))
        reasons.append(f"found submission email(s): {', '.join(found_emails[:5])}")

    for phrase in NON_EMAIL_ONLY_PHRASES:
        if phrase in text:
            confidence -= 25
            reasons.append(f"non-email submission signal: {phrase}")

    # Strong rule:
    # If an explicit email exists and at least one email-submission phrase exists,
    # treat as allowed.
    has_email_phrase = any(phrase in text for phrase in EMAIL_SUBMISSION_PHRASES)
    allows_email = bool(found_emails) and has_email_phrase

    # Soft rule:
    # If email exists and wording strongly suggests response/contact routing, accept.
    if not allows_email and found_emails:
        soft_signals = [
            "for enquiries",
            "for submission",
            "submit to",
            "quotation to",
            "rfq to",
            "bid to",
            "proposal to",
            "responses to",
        ]
        if any(sig in text for sig in soft_signals):
            confidence += 10
            reasons.append("email present with soft submission/context signal")
            allows_email = confidence >= 25

    confidence = max(0, min(100, confidence))

    # Final fallback:
    if allows_email is False and confidence >= 40 and found_emails:
        allows_email = True
        reasons.append("confidence threshold met for email submission")

    return {
        "allows_email_submission": allows_email,
        "submission_emails": found_emails,
        "email_submission_confidence": confidence,
        "email_submission_reasons": reasons[:20],
    }
