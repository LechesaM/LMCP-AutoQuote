from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Set

from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.pilot_operator_session_service import PilotOperatorSessionService
from app.services.pilot_readiness_declaration_service import PilotReadinessDeclarationService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"

PILOT_SCOPE_KEYWORDS = {
    "supply",
    "delivery",
    "goods",
    "consumables",
    "stationery",
    "office",
    "ppe",
}

RESTRICTED_CATEGORY_KEYWORDS = {
    "catering",
    "medical",
    "medical consumables",
    "pharmaceutical",
    "fuel",
    "petrol",
    "diesel",
    "it equipment",
    "information technology",
    "computer equipment",
    "laptop",
    "construction",
    "engineering",
    "professional services",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: Any) -> str:
    return " ".join(_safe_str(text, "").lower().replace("/", " ").replace("-", " ").split())


def _contains_any(text: str, tokens: Set[str]) -> bool:
    return any(token in text for token in tokens)


def _eligible_scope(item_blob: str, rfq_id: str) -> bool:
    if rfq_id.startswith("REHEARSAL-"):
        return True
    return _contains_any(item_blob, PILOT_SCOPE_KEYWORDS)


def _restricted_category(item_blob: str) -> bool:
    return _contains_any(item_blob, RESTRICTED_CATEGORY_KEYWORDS)


def _safe_score(*scores: float) -> float:
    values = [max(0.0, min(100.0, _safe_float(score, 0.0))) for score in scores]
    return round(mean(values), 2) if values else 0.0


class SupervisedRfqIntakeService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
    ) -> None:
        cycle_root = cycle_root or PILOT_CYCLE_ROOT
        export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.operator_sessions = PilotOperatorSessionService(cycle_root=cycle_root, export_root=export_root)
        self.readiness = PilotReadinessDeclarationService(cycle_root=cycle_root, export_root=export_root)
        self.lifecycle = RfqLifecycleService()

    def _latest_session(self) -> Dict[str, Any]:
        response = self.operator_sessions.latest_operator_session()
        return _safe_dict(response.get("operator_session"))

    def _latest_readiness(self) -> Dict[str, Any]:
        response = self.readiness.latest_declaration()
        if response.get("status") == "not_found":
            return {}
        return response

    def _rfq_item(self, rfq_id: str) -> Dict[str, Any]:
        try:
            response = self.lifecycle.get_item(rfq_id)
        except Exception:
            return {}
        return _safe_dict(response.get("item"))

    def _intake_for_assignment(self, assignment: Dict[str, Any], session: Dict[str, Any], readiness: Dict[str, Any]) -> Dict[str, Any]:
        rfq_id = _safe_str(assignment.get("rfq_id"), "unknown")
        item = self._rfq_item(rfq_id)
        generated_at = _safe_str(session.get("generated_at"), _now_iso())
        cycle_id = _safe_str(session.get("cycle_id"), "")
        title = _safe_str(item.get("title") or item.get("name") or item.get("description"), "")
        category = _normalize(item.get("category") or item.get("classification") or item.get("scope") or assignment.get("category"))
        item_blob = _normalize(" ".join([rfq_id, title, category, _safe_str(item.get("buyer_name"), ""), _safe_str(item.get("buyer"), ""), _safe_str(item.get("description"), "")]))
        restricted = _restricted_category(item_blob)
        scope_valid = _eligible_scope(item_blob, rfq_id) and not restricted
        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        supervision_score = _safe_float(session.get("operator_supervision_score"), 0.0)
        supervision_window = _safe_dict(session.get("supervision_window"))
        operator_ack = _safe_dict(session.get("operator_acknowledgement"))
        supervision_capacity_ok = (
            supervision_score >= 85.0
            and _safe_float(_safe_dict(session.get("supervision_coverage")).get("coverage_rate"), 0.0) >= 100.0
            and _safe_list(session.get("pending_approval_checkpoints")) == []
            and bool(operator_ack.get("acknowledged", False))
            and bool(_safe_dict(supervision_window).get("active", False))
        )
        governance_approval_gate = (
            readiness_status == "READY_FOR_CONTROLLED_PILOT"
            and readiness_score >= 85.0
            and _safe_str(readiness.get("declaration_rationale_summary", {}).get("no_go_status"), "PASS") == "PASS"
            and bool(operator_ack.get("acknowledged", False))
            and _safe_list(operator_ack.get("approved_rehearsal_sequence")) == [
                "operator_review",
                "governance_checkpoint",
                "cadence_verification",
                "readiness_verification",
                "evidence_pack_validation",
            ]
        )
        operator_assignment_ready = bool(session.get("active_operator_session")) and governance_approval_gate and supervision_capacity_ok
        intake_eligibility_score = _safe_score(
            100.0 if scope_valid else 0.0,
            100.0 if supervision_capacity_ok else 55.0,
            100.0 if governance_approval_gate else 50.0,
            100.0 if operator_assignment_ready else 55.0,
            100.0 if readiness_status == "READY_FOR_CONTROLLED_PILOT" else 65.0 if readiness_status == "WATCH" else 0.0,
        )
        if restricted or readiness_status == "NO_GO" or not governance_approval_gate:
            intake_decision = "block_intake"
            intake_status = "blocked"
        elif not scope_valid or not supervision_capacity_ok or readiness_status == "WATCH":
            intake_decision = "watch_intake"
            intake_status = "watch"
        else:
            intake_decision = "approve_intake"
            intake_status = "ok"
        warnings = []
        if restricted:
            warnings.append("restricted_category_warning")
        if not scope_valid:
            warnings.append("pilot_scope_warning")
        if not supervision_capacity_ok:
            warnings.append("supervision_capacity_warning")
        if not governance_approval_gate:
            warnings.append("governance_approval_warning")
        if not operator_assignment_ready:
            warnings.append("operator_assignment_warning")
        if readiness_status == "NO_GO":
            warnings.append("readiness_no_go_warning")
        return {
            "intake_id": f"{cycle_id}:{rfq_id}:intake",
            "rfq_id": rfq_id,
            "cycle_id": cycle_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "rfq_category": category or "unknown",
            "rfq_category_source": "lifecycle_item" if category else "rehearsal_scope",
            "pilot_scope_enforced": scope_valid,
            "restricted_category": restricted,
            "restricted_category_warning": restricted,
            "restricted_category_indicators": {
                "restricted_keywords_present": restricted,
                "restricted_category_match": restricted,
            },
            "supervision_capacity_validation": supervision_capacity_ok,
            "supervision_capacity_indicators": {
                "operator_session_active": bool(session.get("active_operator_session")),
                "supervision_score": supervision_score,
                "coverage_rate": _safe_float(_safe_dict(session.get("supervision_coverage")).get("coverage_rate"), 0.0),
                "pending_approval_count": len(_safe_list(session.get("pending_approval_checkpoints"))),
                "supervision_window_active": bool(supervision_window.get("active", False)),
            },
            "governance_approval_gating": governance_approval_gate,
            "operator_assignment_readiness": operator_assignment_ready,
            "intake_eligibility_score": intake_eligibility_score,
            "intake_decision": intake_decision,
            "intake_status": intake_status,
            "intake_decision_reason": [
                f"category={category or 'unknown'}",
                f"scope_valid={scope_valid}",
                f"restricted_category={restricted}",
                f"supervision_capacity_ok={supervision_capacity_ok}",
                f"governance_approval_gate={governance_approval_gate}",
                f"operator_assignment_ready={operator_assignment_ready}",
                f"readiness_status={readiness_status}",
            ],
            "intake_decision_history": [
                {
                    "intake_id": f"{cycle_id}:{rfq_id}:intake",
                    "decision": intake_decision,
                    "score": intake_eligibility_score,
                    "generated_at": generated_at,
                }
            ],
            "operator_session_id": _safe_str(session.get("operator_session_id"), ""),
            "operator_name": _safe_str(session.get("operator_name"), "staging-governance-operator"),
            "operator_role": _safe_str(session.get("operator_role"), "governance_reviewer"),
            "readiness_declaration_status": readiness_status,
            "readiness_declaration_grade": _safe_str(readiness.get("declaration_grade"), "watch"),
            "readiness_declaration_score": readiness_score,
            "governance_approval_state": "approved" if governance_approval_gate else "pending",
            "intake_warning_indicators": {
                "restricted_category_warning": restricted,
                "pilot_scope_warning": not scope_valid,
                "supervision_capacity_warning": not supervision_capacity_ok,
                "governance_approval_warning": not governance_approval_gate,
                "operator_assignment_warning": not operator_assignment_ready,
                "readiness_no_go_warning": readiness_status == "NO_GO",
            },
            "warnings": warnings,
        }

    def _session_records(self, limit: int = 20) -> List[Dict[str, Any]]:
        session_history = _safe_list(self.operator_sessions.operator_session_history(limit=limit).get("operator_session_history", []))
        readiness = self._latest_readiness()
        records: List[Dict[str, Any]] = []
        for session in session_history:
            assignments = _safe_list(session.get("supervised_rfq_assignments"))
            for assignment in assignments:
                if not isinstance(assignment, dict):
                    continue
                records.append(self._intake_for_assignment(assignment, session, readiness))
        records.sort(key=lambda item: (_safe_str(item.get("generated_at"), ""), _safe_str(item.get("intake_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_intake(self, limit: int = 20) -> Dict[str, Any]:
        records = self._session_records(limit=limit)
        latest = records[0] if records else {}
        decision_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("intake_decision"), "watch_intake")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        restricted_count = sum(1 for record in records if record.get("restricted_category"))
        capacity_warnings = sum(1 for record in records if not record.get("supervision_capacity_validation"))
        approval_warnings = sum(1 for record in records if not record.get("governance_approval_gating"))
        score_values = [_safe_float(record.get("intake_eligibility_score"), 0.0) for record in records]
        if not records:
            status = "not_found"
        elif any(record.get("intake_status") == "blocked" for record in records):
            status = "blocked"
        elif any(record.get("intake_status") == "watch" for record in records):
            status = "watch"
        else:
            status = "ok"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "intake_status": status,
            "intake_eligibility_score": round(mean(score_values), 2) if score_values else 0.0,
            "intake_eligibility_grade": "ready" if score_values and mean(score_values) >= 90.0 else "watch" if score_values and mean(score_values) >= 75.0 else "blocked",
            "restricted_category_warnings": [
                record["rfq_id"]
                for record in records
                if record.get("restricted_category_warning")
            ],
            "supervision_capacity_indicators": {
                "coverage_ok": not bool(capacity_warnings),
                "capacity_warning_count": capacity_warnings,
                "operator_assignment_ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
                "active_session_count": sum(1 for record in records if record.get("operator_session_id")),
            },
            "governance_intake_decisions": records,
            "intake_decision_history": records,
            "intake_decision_counts": decision_counts,
            "pilot_scope_enforcement": {
                "pilot_scope_valid_count": sum(1 for record in records if record.get("pilot_scope_enforced")),
                "pilot_scope_invalid_count": sum(1 for record in records if not record.get("pilot_scope_enforced")),
                "restricted_category_count": restricted_count,
            },
            "operator_assignment_readiness_summary": {
                "ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
                "not_ready_count": sum(1 for record in records if not record.get("operator_assignment_readiness")),
                "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
                "governance_approval_block_count": approval_warnings,
            },
            "latest_intake": latest,
            "warning_indicators": {
                "restricted_category_warning": bool(restricted_count),
                "supervision_capacity_warning": bool(capacity_warnings),
                "governance_approval_warning": bool(approval_warnings),
                "intake_blocked_warning": status == "blocked",
            },
            "warnings": [
                warning
                for warning in [
                    "restricted_category_warning" if restricted_count else "",
                    "supervision_capacity_warning" if capacity_warnings else "",
                    "governance_approval_warning" if approval_warnings else "",
                    "intake_blocked_warning" if status == "blocked" else "",
                ]
                if warning
            ],
        }

    def latest_intake(self) -> Dict[str, Any]:
        response = self.list_intake(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No supervised RFQ intake records have been recorded yet.",
                "intake": {},
            }
        latest = _safe_dict(response.get("latest_intake"))
        assignment_summary = _safe_dict(response.get("operator_assignment_readiness_summary"))
        return {
            "status": response.get("status", "ok"),
            "intake_status": response.get("intake_status", "watch"),
            "intake_eligibility_score": response.get("intake_eligibility_score", 0.0),
            "intake_eligibility_grade": response.get("intake_eligibility_grade", "watch"),
            "latest_intake": latest,
            "governance_approval_gating": bool(latest.get("governance_approval_gating", False)),
            "restricted_category_warning": bool(latest.get("restricted_category_warning", False)),
            "pilot_scope_enforced": bool(latest.get("pilot_scope_enforced", False)),
            "supervision_capacity_validation": bool(latest.get("supervision_capacity_validation", False)),
            "operator_assignment_readiness": bool(_safe_int(assignment_summary.get("ready_count"), 0) > 0),
            "operator_assignment_readiness_summary": assignment_summary,
            "governance_intake_decisions": response.get("governance_intake_decisions", []),
            "intake_decision_history": response.get("intake_decision_history", []),
            "restricted_category_warnings": response.get("restricted_category_warnings", []),
            "supervision_capacity_indicators": response.get("supervision_capacity_indicators", {}),
            "pilot_scope_enforcement": response.get("pilot_scope_enforcement", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def intake_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_intake(limit=limit)
        latest = _safe_dict(response.get("latest_intake"))
        assignment_summary = _safe_dict(response.get("operator_assignment_readiness_summary"))
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("intake_decision_history", [])),
            "latest_intake": latest,
            "governance_approval_gating": bool(latest.get("governance_approval_gating", False)),
            "restricted_category_warning": bool(latest.get("restricted_category_warning", False)),
            "pilot_scope_enforced": bool(latest.get("pilot_scope_enforced", False)),
            "supervision_capacity_validation": bool(latest.get("supervision_capacity_validation", False)),
            "operator_assignment_readiness": bool(_safe_int(assignment_summary.get("ready_count"), 0) > 0),
            "operator_assignment_readiness_summary": assignment_summary,
            "intake_decision_history": response.get("intake_decision_history", []),
            "governance_intake_decisions": response.get("governance_intake_decisions", []),
            "restricted_category_warnings": response.get("restricted_category_warnings", []),
            "supervision_capacity_indicators": response.get("supervision_capacity_indicators", {}),
            "pilot_scope_enforcement": response.get("pilot_scope_enforcement", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
