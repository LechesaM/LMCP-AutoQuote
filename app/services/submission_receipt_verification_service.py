from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from app.services.submission_execution_service import build_submission_execution_state


def _clean(value: Any) -> str:
    return str(value or "").strip()


def build_signed_receipt_verification_report(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    tender_id = _clean(payload.get("tender_id") or "RFQ")
    execution = build_submission_execution_state({"tender_id": tender_id})
    verified = bool(Path(execution.get("receiptJsonPath") or "").exists())
    return {
        "tender_id": tender_id,
        "verification": {
            "verified": verified,
            "signature_verification": {"verified": verified, "status": "ok" if verified else "missing"},
        },
        "status": "ok" if verified else "missing",
        "blockers": [] if verified else ["receipt missing"],
    }
