from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.autonomous_submission_governance import autonomous_submission_authorization
from app.services.submission_history_service import (
    list_submission_history,
    update_submission_event,
)

from app.services.email_submission_service import submit_quote_email
from app.services.tender_submission_pipeline import submit_tender_to_portal

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _can_retry(item: Dict[str, Any]) -> bool:
    status = str(item.get("status") or "").lower()
    retry_count = int(item.get("retry_count") or 0)

    if retry_count >= MAX_RETRIES:
        return False

    return status in {"failed", "manual_action_required"}


def _build_retry_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rebuild minimal payload required to retry submission
    """
    return {
        "buyer_name": item.get("buyer_name"),
        "buyer_rfq_number": item.get("buyer_rfq_number"),
        "quote_number": item.get("quote_number"),
        "recipient_email": item.get("recipient_email"),
        "submission_method": item.get("submission_method"),
        "portal_url": item.get("metadata", {}).get("portal_url"),
        "final_pdf_path": item.get("document_path"),
        "attachment_paths": _safe_list(item.get("attachments")),
        "retry_count": int(item.get("retry_count") or 0) + 1,
    }


def retry_failed_submissions(limit: int = 10) -> Dict[str, Any]:
    governance = autonomous_submission_authorization()
    if not governance["authorized"]:
        return {
            "retried": [],
            "skipped": [],
            "total_retried": 0,
            "status": "governance_blocked",
            "reason": governance["reason"],
        }

    history = list_submission_history(limit=500, offset=0)
    items = history.get("items", [])

    retried = []
    skipped = []

    for item in items:
        if not _can_retry(item):
            continue

        payload = _build_retry_payload(item)
        method = str(item.get("submission_method") or "").lower()

        try:
            if method == "email":
                result = submit_quote_email(payload)

            elif method == "portal":
                result = submit_tender_to_portal(payload)

            else:
                skipped.append({
                    "id": item.get("id"),
                    "reason": f"Unsupported method: {method}"
                })
                continue

            update_submission_event(
                item.get("id"),
                {
                    "status": result.get("status"),
                    "status_message": result.get("message") or result.get("error"),
                    "retry_count": payload["retry_count"],
                }
            )

            retried.append({
                "id": item.get("id"),
                "status": result.get("status"),
            })

            if len(retried) >= limit:
                break

        except Exception as exc:
            logger.warning("Retry failed for %s: %s", item.get("id"), exc)

    return {
        "retried": retried,
        "skipped": skipped,
        "total_retried": len(retried),
    }
