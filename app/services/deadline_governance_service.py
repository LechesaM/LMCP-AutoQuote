from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.pilot_operator_session_service import PilotOperatorSessionService
from app.services.pilot_readiness_declaration_service import PilotReadinessDeclarationService
from app.services.physical_submission_governance_service import PhysicalSubmissionGovernanceService
from app.services.packaging_governance_service import PackagingGovernanceService
from app.services.submission_modality_governance_service import SubmissionModalityGovernanceService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value, "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _deadline_from_item(item: Dict[str, Any]) -> str:
    for key in ("submission_deadline", "deadline", "closing_date", "closing_datetime", "closing_at", "due_date"):
        value = _safe_str(item.get(key), "")
        if value:
            return value
    pack = _safe_dict(item.get("submission_pack"))
    for key in ("submission_deadline", "deadline", "closing_date", "closing_at"):
        value = _safe_str(pack.get(key), "")
        if value:
            return value
    return ""


class DeadlineGovernanceService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
    ) -> None:
        cycle_root = cycle_root or PILOT_CYCLE_ROOT
        export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.operator_sessions = PilotOperatorSessionService(cycle_root=cycle_root, export_root=export_root)
        self.readiness = PilotReadinessDeclarationService(cycle_root=cycle_root, export_root=export_root)
        self.physical = PhysicalSubmissionGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.packaging = PackagingGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.modality = SubmissionModalityGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.lifecycle = RfqLifecycleService()

    def _latest_session(self) -> Dict[str, Any]:
        response = self.operator_sessions.latest_operator_session()
        return _safe_dict(response.get("operator_session"))

    def _latest_readiness(self) -> Dict[str, Any]:
        response = self.readiness.latest_declaration()
        return response if isinstance(response, dict) and response.get("status") != "not_found" else {}

    def _item(self, item: Dict[str, Any], session: Dict[str, Any], readiness: Dict[str, Any]) -> Dict[str, Any]:
        rfq_id = _safe_str(item.get("rfq_id"), "unknown")
        generated_at = _safe_str(item.get("updated_at") or item.get("generated_at") or session.get("generated_at"), _now_iso())
        title = _safe_str(item.get("title") or item.get("name") or item.get("description"), "")
        deadline = _deadline_from_item(item)
        deadline_dt = _parse_iso(deadline)
        now = datetime.now(timezone.utc)
        hours_to_deadline = round((deadline_dt - now).total_seconds() / 3600.0, 2) if deadline_dt else None

        packaging = _safe_dict(self.packaging.latest_packaging_governance())
        modality = _safe_dict(self.modality.latest_submission_modality())
        physical = _safe_dict(self.physical.latest_physical_submission())

        submission_bundle_ready = bool(_safe_dict(packaging.get("latest_packaging_governance")).get("submission_bundle_completeness"))
        upload_package_ready = bool(_safe_dict(packaging.get("latest_packaging_governance")).get("upload_package_readiness"))
        physical_required = bool(_safe_dict(physical.get("latest_physical_submission")).get("physical_submission_required"))
        selected_modality = _safe_str(modality.get("selected_modality"), "unsupported")
        courier_required = selected_modality == "physical" or physical_required

        deadline_risk_warnings: List[str] = []
        overdue_indicators = {
            "deadline_missing": not bool(deadline),
            "deadline_invalid": bool(deadline) and deadline_dt is None,
            "deadline_overdue": bool(deadline_dt and deadline_dt < now),
            "deadline_due_soon": bool(deadline_dt and deadline_dt >= now and (deadline_dt - now) <= timedelta(hours=24)),
            "upload_window_closed": not upload_package_ready,
            "portal_timeout_warning": selected_modality == "portal" and not submission_bundle_ready,
            "courier_timing_warning": courier_required and not physical_required,
            "escalation_timing_warning": bool(deadline_dt and (deadline_dt - now) <= timedelta(hours=4)),
            "late_submission_prevention": bool(deadline_dt and deadline_dt <= now),
        }
        if overdue_indicators["deadline_missing"]:
            deadline_risk_warnings.append("deadline_missing_warning")
        if overdue_indicators["deadline_invalid"]:
            deadline_risk_warnings.append("deadline_invalid_warning")
        if overdue_indicators["deadline_overdue"]:
            deadline_risk_warnings.append("deadline_overdue_warning")
        if overdue_indicators["deadline_due_soon"]:
            deadline_risk_warnings.append("deadline_due_soon_warning")
        if overdue_indicators["upload_window_closed"]:
            deadline_risk_warnings.append("upload_window_closed_warning")
        if overdue_indicators["portal_timeout_warning"]:
            deadline_risk_warnings.append("portal_timeout_warning")
        if overdue_indicators["courier_timing_warning"]:
            deadline_risk_warnings.append("courier_timing_warning")
        if overdue_indicators["escalation_timing_warning"]:
            deadline_risk_warnings.append("escalation_timing_warning")

        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        supervision_window_active = bool(_safe_dict(session.get("supervision_window")).get("active", False))
        operator_ack = bool(_safe_dict(session.get("operator_acknowledgement")).get("acknowledged", False))
        supervision_ok = bool(session.get("active_operator_session")) and supervision_window_active and operator_ack
        readiness_ok = readiness_status == "READY_FOR_CONTROLLED_PILOT" and readiness_score >= 85.0
        governance_gate = readiness_ok and supervision_ok

        timing_readiness_score = round(
            mean(
                [
                    100.0 if deadline_dt and deadline_dt > now else 35.0,
                    100.0 if submission_bundle_ready else 45.0,
                    100.0 if upload_package_ready else 45.0,
                    100.0 if not overdue_indicators["deadline_overdue"] else 40.0,
                    100.0 if not overdue_indicators["late_submission_prevention"] else 35.0,
                    100.0 if governance_gate else 50.0,
                ]
            ),
            2,
        )

        hard_blockers = (
            overdue_indicators["deadline_missing"],
            overdue_indicators["deadline_invalid"],
            overdue_indicators["deadline_overdue"],
            overdue_indicators["late_submission_prevention"],
        )
        watch_only = (
            overdue_indicators["deadline_due_soon"],
            overdue_indicators["upload_window_closed"],
            overdue_indicators["portal_timeout_warning"],
            overdue_indicators["courier_timing_warning"],
            overdue_indicators["escalation_timing_warning"],
        )

        if not governance_gate or any(hard_blockers):
            governance_status = "blocked"
            decision = "block_deadline_governance"
        elif any(watch_only) or deadline_risk_warnings:
            governance_status = "watch"
            decision = "watch_deadline_governance"
        else:
            governance_status = "ok"
            decision = "approve_deadline_governance"

        return {
            "deadline_governance_id": f"{rfq_id}:deadline-governance",
            "rfq_id": rfq_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "submission_cutoff_tracking": {
                "deadline": deadline,
                "hours_to_deadline": hours_to_deadline,
                "deadline_overdue": overdue_indicators["deadline_overdue"],
                "deadline_due_soon": overdue_indicators["deadline_due_soon"],
            },
            "upload_window_governance": {
                "upload_package_ready": upload_package_ready,
                "upload_window_open": upload_package_ready and not overdue_indicators["deadline_overdue"],
            },
            "courier_timing_governance": {
                "courier_required": courier_required,
                "courier_timing_warning": overdue_indicators["courier_timing_warning"],
            },
            "portal_timeout_governance": {
                "selected_modality": selected_modality,
                "portal_timeout_warning": overdue_indicators["portal_timeout_warning"],
            },
            "escalation_timing_governance": {
                "escalation_timing_warning": overdue_indicators["escalation_timing_warning"],
                "escalation_window_hours": 4,
            },
            "late_submission_prevention": overdue_indicators["late_submission_prevention"],
            "deadline_risk_warnings": deadline_risk_warnings,
            "overdue_submission_indicators": overdue_indicators,
            "congestion_window_indicators": {
                "submission_bundle_ready": submission_bundle_ready,
                "upload_package_ready": upload_package_ready,
                "physical_submission_ready": physical.get("latest_physical_submission", {}).get("physical_submission_required", False),
            },
            "timing_readiness_score": timing_readiness_score,
            "deadline_governance_status": governance_status,
            "deadline_governance_decision": decision,
            "deadline_governance_decision_reason": [
                f"deadline_present={bool(deadline)}",
                f"deadline_overdue={overdue_indicators['deadline_overdue']}",
                f"deadline_due_soon={overdue_indicators['deadline_due_soon']}",
                f"submission_bundle_ready={submission_bundle_ready}",
                f"upload_package_ready={upload_package_ready}",
                f"governance_gate={governance_gate}",
            ],
            "submission_deadline_governance_history": [
                {
                    "deadline_governance_id": f"{rfq_id}:deadline-governance",
                    "decision": decision,
                    "score": timing_readiness_score,
                    "generated_at": generated_at,
                }
            ],
            "operator_assignment_readiness": supervision_ok and readiness_ok,
            "governance_approval_gating": governance_gate,
            "warnings": deadline_risk_warnings + (["readiness_no_go_warning"] if readiness_status == "NO_GO" else []),
            "readiness_declaration_status": readiness_status,
            "readiness_declaration_score": readiness_score,
            "operator_session_id": _safe_str(session.get("operator_session_id"), ""),
        }

    def _records(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = _safe_list(self.lifecycle.list_items(limit=250).get("items", []))
        session = self._latest_session()
        readiness = self._latest_readiness()
        records: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not _deadline_from_item(item) and not any(_safe_str(item.get(key), "") for key in ("submission_pack", "title", "description")):
                continue
            records.append(self._item(item, session, readiness))
        records.sort(key=lambda record: (_safe_str(record.get("generated_at"), ""), _safe_str(record.get("deadline_governance_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_deadline_governance(self, limit: int = 20) -> Dict[str, Any]:
        records = self._records(limit=limit)
        latest = records[0] if records else {}
        scores = [_safe_float(record.get("timing_readiness_score"), 0.0) for record in records]
        decision_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("deadline_governance_decision"), "watch_deadline_governance")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        status = "ok"
        if not records:
            status = "not_found"
        elif any(record.get("deadline_governance_status") == "blocked" for record in records):
            status = "blocked"
        elif any(record.get("deadline_governance_status") == "watch" for record in records):
            status = "watch"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "deadline_governance_status": status,
            "timing_readiness_score": round(mean(scores), 2) if scores else 0.0,
            "submission_cutoff_warning_count": sum(1 for record in records if record.get("deadline_risk_warnings")),
            "upload_window_open_count": sum(1 for record in records if record.get("upload_window_governance", {}).get("upload_window_open")),
            "courier_timing_warning_count": sum(1 for record in records if record.get("courier_timing_governance", {}).get("courier_timing_warning")),
            "portal_timeout_warning_count": sum(1 for record in records if record.get("portal_timeout_governance", {}).get("portal_timeout_warning")),
            "escalation_timing_warning_count": sum(1 for record in records if record.get("escalation_timing_governance", {}).get("escalation_timing_warning")),
            "late_submission_prevention_count": sum(1 for record in records if record.get("late_submission_prevention")),
            "deadline_governance_decision_counts": decision_counts,
            "deadline_governance_history": records,
            "latest_deadline_governance": latest,
            "operator_assignment_readiness_summary": {
                "ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
                "not_ready_count": sum(1 for record in records if not record.get("operator_assignment_readiness")),
                "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
            },
            "warnings": [
                warning
                for warning in [
                    "deadline_risk_warning" if any(record.get("deadline_risk_warnings") for record in records) else "",
                    "overdue_submission_warning" if any(record.get("overdue_submission_indicators", {}).get("deadline_overdue") for record in records) else "",
                    "congestion_window_warning" if any(record.get("congestion_window_indicators", {}).get("upload_package_ready") is False for record in records) else "",
                ]
                if warning
            ],
        }

    def latest_deadline_governance(self) -> Dict[str, Any]:
        response = self.list_deadline_governance(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No deadline governance records have been recorded yet.",
                "deadline_governance": {},
            }
        return {
            "status": response.get("status", "ok"),
            "deadline_governance_status": response.get("deadline_governance_status", "watch"),
            "timing_readiness_score": response.get("timing_readiness_score", 0.0),
            "latest_deadline_governance": response.get("latest_deadline_governance", {}),
            "deadline_governance_history": response.get("deadline_governance_history", []),
            "deadline_governance_decision_counts": response.get("deadline_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }

    def deadline_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_deadline_governance(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("deadline_governance_history", [])),
            "deadline_governance_history": response.get("deadline_governance_history", []),
            "deadline_governance_decision_counts": response.get("deadline_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }
