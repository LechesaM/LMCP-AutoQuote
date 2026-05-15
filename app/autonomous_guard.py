from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.models import Opportunity, QuoteDraft


def safe_get(obj: object, field_name: str, default=None):
    return getattr(obj, field_name, default)


def text_value(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_email_like(value: str) -> bool:
    value = text_value(value)
    return "@" in value and "." in value


def quote_status_allows_submission(status: str) -> bool:
    status = text_value(status).lower()
    blocked = {
        "",
        "cancelled",
        "void",
        "rejected",
        "failed",
        "draft_incomplete",
        "incomplete",
    }
    return status not in blocked


def opportunity_has_email_destination(opportunity: Opportunity) -> bool:
    email = text_value(safe_get(opportunity, "email", ""))
    submission_method = text_value(safe_get(opportunity, "submission_method", "")).lower()

    if is_email_like(email):
        return True

    if "email" in submission_method:
        return True

    return False


def opportunity_score_allows_processing(opportunity: Opportunity, min_score: int = 70) -> bool:
    score = safe_get(opportunity, "relevance_score", 0) or 0
    try:
        score = float(score)
    except Exception:
        score = 0
    return score >= min_score


def opportunity_not_closed(opportunity: Opportunity) -> bool:
    closing_date = safe_get(opportunity, "closing_date", None)
    if closing_date is None:
        return True
    return True


def quote_has_minimum_fields(quote: QuoteDraft) -> bool:
    quote_number = text_value(safe_get(quote, "quote_number", ""))
    total_amount = safe_get(quote, "total_amount", 0) or 0
    status = text_value(safe_get(quote, "status", ""))

    if not quote_number:
        return False

    try:
        total_amount = float(total_amount)
    except Exception:
        total_amount = 0

    if total_amount <= 0:
        return False

    if not quote_status_allows_submission(status):
        return False

    return True


def quote_not_already_submitted(quote: QuoteDraft) -> bool:
    status = text_value(safe_get(quote, "status", "")).lower()
    submitted_markers = {
        "submitted",
        "sent",
        "emailed",
        "delivered",
        "completed",
    }
    return status not in submitted_markers


def collect_guard_failures(opportunity: Opportunity, quote: QuoteDraft | None) -> List[str]:
    failures: List[str] = []

    if not opportunity_score_allows_processing(opportunity):
        failures.append("opportunity score below threshold")

    if not opportunity_has_email_destination(opportunity):
        failures.append("no valid email submission destination")

    if not opportunity_not_closed(opportunity):
        failures.append("opportunity appears closed")

    if quote is None:
        failures.append("quote not found")
        return failures

    if not quote_has_minimum_fields(quote):
        failures.append("quote is incomplete or invalid")

    if not quote_not_already_submitted(quote):
        failures.append("quote already submitted")

    return failures


def evaluate_submission_readiness(
    opportunity: Opportunity,
    quote: QuoteDraft | None,
) -> Tuple[bool, Dict[str, Any]]:
    failures = collect_guard_failures(opportunity, quote)

    return (
        len(failures) == 0,
        {
            "ready": len(failures) == 0,
            "failures": failures,
            "opportunity_id": safe_get(opportunity, "id", None),
            "quote_id": safe_get(quote, "id", None) if quote else None,
        },
    )
