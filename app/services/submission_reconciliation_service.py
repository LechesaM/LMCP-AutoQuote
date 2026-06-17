from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from app.services.external_audit_export_service import build_external_audit_export_report
from app.services.submission_execution_service import build_submission_execution_state


def reconcile_submission_execution(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    execution = build_submission_execution_state(payload)
    audit_export = build_external_audit_export_report(payload)
    blockers = list(execution.get("blockers") or [])
    if not audit_export.get("ready"):
        blockers.append("external audit export unavailable")
    return {
        "status": "ok" if not blockers else "blocked",
        "execution": execution,
        "audit_export": audit_export,
        "blockers": blockers,
    }
