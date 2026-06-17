from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from app.services.rfq_state_store import RfqStateStore, utc_now_iso


STUCK_STATES = {
    "DISCOVERED",
    "QUALIFIED",
    "DOCUMENTS_ACQUIRED",
    "DOCUMENTS_PARSED",
    "PRICED",
    "SBD_COMPLETED",
    "QUOTE_PACK_READY",
    "SUBMISSION_READY",
}


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def classify_failure(reason: str) -> str:
    text = str(reason or "").lower()
    if any(token in text for token in ["captcha", "login", "forbidden", "401", "403"]):
        return "portal_access"
    if any(token in text for token in ["timeout", "stuck", "retry"]):
        return "timeout_or_stuck"
    if any(token in text for token in ["margin", "profit", "briefing", "catering", "medical", "diesel", "petrol", "it equipment"]):
        return "policy_block"
    if any(token in text for token in ["document", "pdf", "docx", "xlsx", "parse"]):
        return "document_processing"
    return "general_failure"


class RfqRecoveryService:
    def __init__(self, store: RfqStateStore | None = None) -> None:
        self.store = store or RfqStateStore()

    def recover_stuck(self, timeout_minutes: int = 120) -> Dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, int(timeout_minutes)))
        recovered: List[Dict[str, Any]] = []
        untouched = 0
        for item in self.store.list_items():
            updated_at = _parse_iso(str(item.get("updated_at") or item.get("created_at") or utc_now_iso()))
            if item.get("current_state") in STUCK_STATES and updated_at < cutoff:
                item["previous_state"] = item.get("current_state")
                item["current_state"] = "REVIEW_REQUIRED"
                item["failure_reason"] = "stuck_timeout_requires_operator_review"
                item["failure_classification"] = classify_failure(item["failure_reason"])
                item["updated_at"] = utc_now_iso()
                item.setdefault("audit_log", []).append(
                    {
                        "at": utc_now_iso(),
                        "event": "recover_stuck",
                        "from_state": item.get("previous_state"),
                        "to_state": "REVIEW_REQUIRED",
                        "reason": item["failure_reason"],
                    }
                )
                recovered.append(item)
            else:
                untouched += 1
        if recovered:
            self.store.update_many(recovered, {"recovered": len(recovered)})
            self.store.append_audit_events(
                [
                    row
                    for item in recovered
                    for row in item.get("audit_log", [])
                    if isinstance(row, dict)
                ]
            )
        return {
            "status": "ok",
            "recovered_count": len(recovered),
            "untouched_count": untouched,
            "timeout_minutes": timeout_minutes,
            "items": recovered,
        }

    def retry_failed(self) -> Dict[str, Any]:
        retried: List[Dict[str, Any]] = []
        exhausted: List[Dict[str, Any]] = []
        for item in self.store.list_items():
            if item.get("current_state") != "FAILED":
                continue
            retries = int(item.get("retries") or 0)
            max_retries = int(item.get("max_retries") or 3)
            if retries >= max_retries:
                exhausted.append(item)
                continue
            item["previous_state"] = "FAILED"
            item["current_state"] = "REVIEW_REQUIRED"
            item["retries"] = retries + 1
            item["updated_at"] = utc_now_iso()
            item.setdefault("audit_log", []).append(
                {
                    "at": utc_now_iso(),
                    "event": "retry_failed",
                    "from_state": "FAILED",
                    "to_state": "REVIEW_REQUIRED",
                    "retry": item["retries"],
                }
            )
            retried.append(item)
        if retried:
            self.store.update_many(retried, {"retried": len(retried)})
            self.store.append_audit_events(
                [
                    row
                    for item in retried
                    for row in item.get("audit_log", [])
                    if isinstance(row, dict)
                ]
            )
        return {
            "status": "ok",
            "retried_count": len(retried),
            "exhausted_count": len(exhausted),
            "retried_items": retried,
            "exhausted_items": exhausted,
        }

    def worker_health_summary(self) -> Dict[str, Any]:
        state = self.store.read()
        items = list(state.get("items", {}).values())
        failed = sum(1 for item in items if item.get("current_state") == "FAILED")
        active = sum(1 for item in items if item.get("current_state") in STUCK_STATES)
        return {
            "queue_ready": True,
            "state_store": str(self.store.state_file),
            "active_items": active,
            "failed_items": failed,
            "throughput": state.get("throughput", {}),
            "celery_task_available": True,
        }
