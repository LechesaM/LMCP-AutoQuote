from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import OperationalExceptionService, _safe_dict, _safe_float, _safe_str


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _format_iso(value: Optional[datetime]) -> str:
    return value.isoformat() if value else ""


def _owner_for_category(category: str) -> str:
    mapping = {
        "transient_failure": "staging-operations",
        "systemic_failure": "platform-reliability",
        "retry_exhaustion": "workflow-operations",
        "telemetry_degradation": "observability",
        "queue_instability": "queue-operations",
        "operator_intervention_anomaly": "operator-governance",
        "governance_compliance_failure": "governance",
    }
    return mapping.get(category, "staging-operations")


def _action_for_category(category: str, message: str) -> str:
    mapping = {
        "transient_failure": "Review transient anomaly evidence and re-run the staged cycle.",
        "systemic_failure": "Restore the affected platform dependency and regenerate the pilot evidence.",
        "retry_exhaustion": "Reduce contention, review retry limits, and re-run the rehearsal.",
        "telemetry_degradation": "Restore telemetry capture and regenerate the governance export.",
        "queue_instability": "Stabilize queue processing and validate the next rehearsal sequence.",
        "operator_intervention_anomaly": "Review operator interventions and re-acknowledge the approved rehearsal sequence.",
        "governance_compliance_failure": "Restore governance compliance and refresh the staging evidence pack.",
    }
    return mapping.get(category, message or "Review the staging evidence and remediate the exception.")


def _deadline_for(category: str, severity: str, detected_at: str) -> str:
    parsed = _parse_iso(detected_at) or datetime.now(timezone.utc)
    offsets = {
        "critical": timedelta(hours=12),
        "high": timedelta(days=1),
        "medium": timedelta(days=2),
        "low": timedelta(days=3),
    }
    if category == "operator_intervention_anomaly":
        offsets["medium"] = timedelta(days=1)
    return _format_iso(parsed + offsets.get(severity, timedelta(days=2)))


def _accepted_risk_classification(category: str, severity: str, open_issue: bool) -> str:
    if not open_issue:
        return "closed"
    if severity in {"high", "critical"} or category == "governance_compliance_failure":
        return "not_accepted"
    return "accepted"


class OperationalRemediationService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
        review_window_days: int = 30,
    ) -> None:
        self.cycle_root = cycle_root or PILOT_CYCLE_ROOT
        self.export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.review_window_days = max(1, review_window_days)
        self._exceptions = OperationalExceptionService(
            cycle_root=self.cycle_root,
            export_root=self.export_root,
            review_window_days=self.review_window_days,
        )

    def _remediation_records(self, limit: int = 20) -> List[Dict[str, Any]]:
        response = self._exceptions.list_exceptions(limit=limit)
        history = list(response.get("classification_history", []))
        unresolved = {record.get("exception_id"): record for record in response.get("unresolved_exception_tracking", [])}
        resolved = {record.get("exception_id"): record for record in response.get("resolved_exception_history", [])}
        records: List[Dict[str, Any]] = []
        for record in history:
            exception_id = _safe_str(record.get("exception_id"), "unknown")
            category = _safe_str(record.get("category"), "transient_failure")
            severity = _safe_str(record.get("severity"), "low")
            detected_at = _safe_str(record.get("detected_at"), _now_iso())
            open_issue = bool(record.get("open_issue", True))
            resolved_record = resolved.get(exception_id)
            unresolved_record = unresolved.get(exception_id)
            remediation_status = "resolved" if resolved_record and not unresolved_record else "open"
            if remediation_status == "resolved":
                completion_status = "completed"
            else:
                completion_status = "overdue" if _parse_iso(_deadline_for(category, severity, detected_at)) and _parse_iso(_deadline_for(category, severity, detected_at)) < datetime.now(timezone.utc) else "in_progress"
            deadline = _deadline_for(category, severity, detected_at)
            overdue = completion_status == "overdue"
            records.append(
                {
                    "remediation_id": f"{exception_id}:remediation",
                    "exception_id": exception_id,
                    "category": category,
                    "source": _safe_str(record.get("source"), ""),
                    "severity": severity,
                    "risk_level": _safe_str(record.get("risk_level"), "medium"),
                    "owner": _owner_for_category(category),
                    "remediation_action": _action_for_category(category, _safe_str(record.get("remediation_action"), "")),
                    "accepted_operational_risk_classification": _accepted_risk_classification(category, severity, open_issue),
                    "remediation_status": remediation_status,
                    "completion_status": completion_status,
                    "blocker_status": "blocking" if open_issue and category in {"governance_compliance_failure", "systemic_failure", "telemetry_degradation", "queue_instability"} else "non_blocking",
                    "deadline_at": deadline,
                    "detected_at": detected_at,
                    "resolved_at": _safe_str(resolved_record.get("resolved_at"), "") if resolved_record else "",
                    "resolved_by_cycle_id": _safe_str(resolved_record.get("resolved_by_cycle_id"), "") if resolved_record else "",
                    "generated_at": _safe_str(record.get("generated_at"), ""),
                    "overdue": overdue,
                    "notes": [
                        f"Category {category} owned by {_owner_for_category(category)}.",
                        f"Remediation deadline {deadline}.",
                    ],
                }
            )
        return records

    def _open_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [record for record in records if record.get("remediation_status") == "open"]

    def _resolved_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [record for record in records if record.get("remediation_status") == "resolved"]

    def _history_summary(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        category_counts: Dict[str, int] = {}
        for record in records:
            category_counts[record["category"]] = category_counts.get(record["category"], 0) + 1
        return {
            "status": "PASS" if not records else "WARN",
            "remediation_count": len(records),
            "category_counts": category_counts,
            "latest_remediation_id": records[0]["remediation_id"] if records else "",
            "latest_deadline_at": records[0]["deadline_at"] if records else "",
            "latest_owner": records[0]["owner"] if records else "",
        }

    def list_remediation(self, limit: int = 20) -> Dict[str, Any]:
        records = self._remediation_records(limit=limit)
        open_records = self._open_records(records)
        resolved_records = self._resolved_records(records)
        overdue_records = [record for record in open_records if record["overdue"]]
        blocked_records = [record for record in open_records if record["blocker_status"] == "blocking"]
        accepted_risk_records = [record for record in records if record["accepted_operational_risk_classification"] == "accepted"]
        history_summary = self._history_summary(records)
        status = "not_found" if not records else ("ok" if not overdue_records and not blocked_records else "watch")
        return {
            "status": status,
            "generated_at": _now_iso(),
            "latest_cycle": self._exceptions.latest_exceptions().get("latest_cycle", {}),
            "latest_governance_export": self._exceptions.latest_exceptions().get("latest_governance_export", {}),
            "remediation_status": status,
            "remediation_summary": {
                "total_remediation_count": len(records),
                "open_remediation_count": len(open_records),
                "resolved_remediation_count": len(resolved_records),
                "overdue_remediation_count": len(overdue_records),
                "blocking_remediation_count": len(blocked_records),
                "accepted_risk_remediation_count": len(accepted_risk_records),
            },
            "remediation_actions": records,
            "open_remediation_tracking": open_records,
            "resolved_remediation_history": resolved_records,
            "unresolved_blocker_tracking": blocked_records,
            "operational_risk_closure_summary": {
                "status": "PASS" if not open_records else "WARN",
                "open_count": len(open_records),
                "closed_count": len(resolved_records),
                "overdue_count": len(overdue_records),
                "accepted_risk_count": len(accepted_risk_records),
            },
            "remediation_governance_history": history_summary,
            "operational_risk_indicators": {
                "overdue_remediation_warning": bool(overdue_records),
                "unresolved_blocker_warning": bool(blocked_records),
                "accepted_risk_warning": bool(accepted_risk_records),
                "history_warning": bool(records),
            },
            "warning_indicators": {
                "overdue_remediation_warning": bool(overdue_records),
                "unresolved_blocker_warning": bool(blocked_records),
                "accepted_risk_warning": bool(accepted_risk_records),
                "history_warning": bool(records),
            },
            "warnings": [
                "overdue_remediation_warning" if overdue_records else "",
                "unresolved_blocker_warning" if blocked_records else "",
                "accepted_risk_warning" if accepted_risk_records else "",
                "history_warning" if records else "",
            ],
        }

    def latest_remediation(self) -> Dict[str, Any]:
        response = self.list_remediation(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No operational remediation records have been generated yet.",
                "remediation": {},
            }
        return {
            "status": response.get("status", "ok"),
            "latest_cycle": response.get("latest_cycle", {}),
            "latest_governance_export": response.get("latest_governance_export", {}),
            "remediation_status": response.get("remediation_status", "watch"),
            "remediation_summary": response.get("remediation_summary", {}),
            "remediation_actions": response.get("remediation_actions", []),
            "open_remediation_tracking": response.get("open_remediation_tracking", []),
            "resolved_remediation_history": response.get("resolved_remediation_history", []),
            "unresolved_blocker_tracking": response.get("unresolved_blocker_tracking", []),
            "operational_risk_closure_summary": response.get("operational_risk_closure_summary", {}),
            "remediation_governance_history": response.get("remediation_governance_history", {}),
            "operational_risk_indicators": response.get("operational_risk_indicators", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def remediation_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_remediation(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("remediation_actions", [])),
            "remediation_actions": response.get("remediation_actions", []),
            "open_remediation_tracking": response.get("open_remediation_tracking", []),
            "resolved_remediation_history": response.get("resolved_remediation_history", []),
            "unresolved_blocker_tracking": response.get("unresolved_blocker_tracking", []),
            "remediation_summary": response.get("remediation_summary", {}),
            "operational_risk_closure_summary": response.get("operational_risk_closure_summary", {}),
            "remediation_governance_history": response.get("remediation_governance_history", {}),
            "operational_risk_indicators": response.get("operational_risk_indicators", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
