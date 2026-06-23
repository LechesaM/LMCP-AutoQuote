from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.compliance_governance_service import ComplianceGovernanceService
from app.services.deadline_governance_service import DeadlineGovernanceService
from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.packaging_governance_service import PackagingGovernanceService
from app.services.physical_submission_governance_service import PhysicalSubmissionGovernanceService
from app.services.pilot_operator_session_service import PilotOperatorSessionService
from app.services.pilot_readiness_declaration_service import PilotReadinessDeclarationService
from app.services.returnable_governance_service import ReturnableGovernanceService
from app.services.signature_governance_service import SignatureGovernanceService
from app.services.submission_modality_governance_service import SubmissionModalityGovernanceService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_is_ready(status: Any) -> bool:
    return _safe_str(status, "").upper() == "READY_FOR_CONTROLLED_PILOT"


def _status_is_ok(status: Any) -> bool:
    return _safe_str(status, "").lower() == "ok"


def _needs_review(statuses: List[bool]) -> bool:
    return any(not value for value in statuses)


class FinalReadinessGovernanceService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
    ) -> None:
        cycle_root = cycle_root or PILOT_CYCLE_ROOT
        export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.readiness = PilotReadinessDeclarationService(cycle_root=cycle_root, export_root=export_root)
        self.operator_sessions = PilotOperatorSessionService(cycle_root=cycle_root, export_root=export_root)
        self.returnable = ReturnableGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.packaging = PackagingGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.compliance = ComplianceGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.signature = SignatureGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.deadline = DeadlineGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.modality = SubmissionModalityGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.physical = PhysicalSubmissionGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.lifecycle = RfqLifecycleService()

    def _latest_response(self, service: Any, method: str) -> Dict[str, Any]:
        response = getattr(service, method)()
        if not isinstance(response, dict):
            return {}
        if response.get("status") == "not_found":
            return {}
        return response

    def _latest_readiness(self) -> Dict[str, Any]:
        response = self.readiness.latest_declaration()
        return response if isinstance(response, dict) and response.get("status") != "not_found" else {}

    def _latest_session(self) -> Dict[str, Any]:
        response = self.operator_sessions.latest_operator_session()
        return _safe_dict(response.get("operator_session"))

    def _component_snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {
            "readiness": self._latest_readiness(),
            "operator_session": self._latest_response(self.operator_sessions, "latest_operator_session"),
            "returnable": self._latest_response(self.returnable, "latest_returnable_governance"),
            "packaging": self._latest_response(self.packaging, "latest_packaging_governance"),
            "compliance": self._latest_response(self.compliance, "latest_compliance_governance"),
            "signature": self._latest_response(self.signature, "latest_signature_governance"),
            "deadline": self._latest_response(self.deadline, "latest_deadline_governance"),
            "modality": self._latest_response(self.modality, "latest_submission_modality"),
            "physical": self._latest_response(self.physical, "latest_physical_submission"),
        }

    def _record(self, item: Dict[str, Any], snapshot: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        rfq_id = _safe_str(item.get("rfq_id"), "unknown")
        generated_at = _safe_str(item.get("updated_at") or item.get("generated_at") or snapshot["operator_session"].get("generated_at"), _now_iso())
        title = _safe_str(item.get("title") or item.get("name") or item.get("description"), "")

        readiness = snapshot["readiness"]
        session_response = snapshot["operator_session"]
        session = _safe_dict(session_response.get("operator_session"))
        returnable = snapshot["returnable"]
        packaging = snapshot["packaging"]
        compliance = snapshot["compliance"]
        signature = snapshot["signature"]
        deadline = snapshot["deadline"]
        modality = snapshot["modality"]
        physical = snapshot["physical"]

        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        readiness_ok = _status_is_ready(readiness_status) and readiness_score >= 85.0

        returnable_status = _safe_str(returnable.get("returnable_governance_status"), "watch")
        packaging_status = _safe_str(packaging.get("packaging_governance_status"), "watch")
        compliance_status = _safe_str(compliance.get("compliance_artifact_governance_status"), "watch")
        signature_status = _safe_str(signature.get("signature_governance_status"), "watch")
        deadline_status = _safe_str(deadline.get("deadline_governance_status"), "watch")
        modality_status = _safe_str(modality.get("modality_governance_status"), "watch")
        physical_status = _safe_str(physical.get("physical_rfq_governance_status"), "watch")

        returnable_ok = _status_is_ok(returnable_status)
        packaging_ok = _status_is_ok(packaging_status)
        compliance_ok = _status_is_ok(compliance_status)
        signature_ok = _status_is_ok(signature_status)
        deadline_ok = _status_is_ok(deadline_status)
        modality_ok = _status_is_ok(modality_status)

        selected_modality = _safe_str(modality.get("selected_modality"), "unsupported")
        physical_required = bool(_safe_dict(physical.get("latest_physical_submission")).get("physical_submission_required")) or selected_modality == "physical"
        physical_ok = (not physical_required) or _status_is_ok(physical_status)

        supervision_window_active = bool(_safe_dict(session.get("supervision_window")).get("active", False))
        operator_acknowledged = bool(_safe_dict(session.get("operator_acknowledgement")).get("acknowledged", False))
        supervision_ok = bool(session.get("active_operator_session")) and supervision_window_active and operator_acknowledged

        final_completeness_ok = returnable_ok and packaging_ok
        final_compliance_ok = compliance_ok and signature_ok
        final_packaging_ok = packaging_ok
        final_timing_ok = deadline_ok
        final_supervision_ok = supervision_ok and readiness_ok
        final_modality_ok = modality_ok and (not physical_required or physical_ok)
        no_go_status = _safe_str(readiness.get("declaration_rationale_summary", {}).get("no_go_status"), _safe_str(readiness.get("no_go_status"), "UNKNOWN"))

        unresolved_blocker_indicators = {
            "final_completeness_blocker": not final_completeness_ok,
            "final_compliance_blocker": not final_compliance_ok,
            "final_packaging_blocker": not final_packaging_ok,
            "final_timing_blocker": not final_timing_ok,
            "final_supervision_blocker": not final_supervision_ok,
            "final_modality_blocker": not final_modality_ok,
            "readiness_blocker": not readiness_ok,
            "no_go_blocker": no_go_status != "PASS",
        }
        unresolved_blocker_count = sum(1 for value in unresolved_blocker_indicators.values() if value)

        overrides = {
            "readiness_override_required": not readiness_ok,
            "completeness_override_required": not final_completeness_ok,
            "compliance_override_required": not final_compliance_ok,
            "packaging_override_required": not final_packaging_ok,
            "timing_override_required": not final_timing_ok,
            "supervision_override_required": not final_supervision_ok,
            "modality_override_required": not final_modality_ok,
            "no_go_override_required": no_go_status != "PASS",
            "blocker_override_required": unresolved_blocker_count > 0,
            "final_override_required": unresolved_blocker_count > 0,
        }

        component_scores = [
            readiness_score,
            _safe_float(returnable.get("bid_response_completeness_score"), 0.0),
            _safe_float(packaging.get("packaging_readiness_score"), 0.0),
            _safe_float(compliance.get("compliance_readiness_score"), 0.0),
            _safe_float(signature.get("signature_governance_score"), 0.0),
            _safe_float(deadline.get("timing_readiness_score"), 0.0),
            _safe_float(modality.get("modality_governance_score"), 0.0),
            _safe_float(physical.get("physical_submission_readiness_score"), 0.0),
            100.0 if final_supervision_ok else 55.0,
        ]
        final_submission_readiness_score = round(mean(component_scores), 2)

        ready_to_submit = (
            final_completeness_ok
            and final_compliance_ok
            and final_packaging_ok
            and final_timing_ok
            and final_supervision_ok
            and final_modality_ok
            and no_go_status == "PASS"
            and unresolved_blocker_count == 0
            and final_submission_readiness_score >= 85.0
        )

        if ready_to_submit:
            final_submission_readiness_status = "READY_TO_SUBMIT"
            decision = "authorise_final_submission"
            governance_status = "ok"
        else:
            final_submission_readiness_status = "NOT_READY_TO_SUBMIT"
            decision = "defer_final_submission"
            governance_status = "blocked" if unresolved_blocker_count > 0 or not readiness_ok else "watch"

        final_escalation_authority = "governance_review_board" if final_submission_readiness_status != "READY_TO_SUBMIT" or overrides["final_override_required"] else "operator_session"
        final_escalation_authority_reason = [
            f"readiness_ok={readiness_ok}",
            f"returnable_ok={returnable_ok}",
            f"packaging_ok={packaging_ok}",
            f"compliance_ok={compliance_ok}",
            f"signature_ok={signature_ok}",
            f"deadline_ok={deadline_ok}",
            f"modality_ok={modality_ok}",
            f"physical_ok={physical_ok}",
            f"supervision_ok={final_supervision_ok}",
            f"no_go_status={no_go_status}",
            f"unresolved_blockers={unresolved_blocker_count}",
        ]

        final_readiness_rationale = [
            f"Final completeness verification: {'PASS' if final_completeness_ok else 'FAIL'}.",
            f"Final compliance verification: {'PASS' if final_compliance_ok else 'FAIL'}.",
            f"Final packaging verification: {'PASS' if final_packaging_ok else 'FAIL'}.",
            f"Final timing verification: {'PASS' if final_timing_ok else 'FAIL'}.",
            f"Final supervision verification: {'PASS' if final_supervision_ok else 'FAIL'}.",
            f"Final modality verification: {'PASS' if final_modality_ok else 'FAIL'}.",
            f"NO-GO status: {no_go_status}.",
        ]
        final_readiness_rationale_history = [
            {
                "final_readiness_id": f"{rfq_id}:final-readiness",
                "decision": decision,
                "status": final_submission_readiness_status,
                "score": final_submission_readiness_score,
                "generated_at": generated_at,
                "rationale": final_readiness_rationale,
            }
        ]

        warnings = [
            warning
            for warning in [
                "not_ready_to_submit_warning" if not ready_to_submit else "",
                "unresolved_blocker_warning" if unresolved_blocker_count > 0 else "",
                "readiness_no_go_warning" if no_go_status != "PASS" else "",
                "modality_warning" if not final_modality_ok else "",
                "timing_warning" if not final_timing_ok else "",
            ]
            if warning
        ]

        return {
            "final_readiness_id": f"{rfq_id}:final-readiness",
            "rfq_id": rfq_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "final_submission_readiness_status": final_submission_readiness_status,
            "final_submission_readiness_score": final_submission_readiness_score,
            "final_submission_readiness_grade": "ready" if final_submission_readiness_status == "READY_TO_SUBMIT" else "not_ready",
            "final_completeness_verification": {
                "returnable_governance_status": returnable_status,
                "packaging_governance_status": packaging_status,
                "returnable_governance_ok": returnable_ok,
                "packaging_governance_ok": packaging_ok,
                "submission_bundle_complete": bool(_safe_dict(packaging.get("latest_packaging_governance")).get("submission_bundle_completeness")),
                "final_completeness_ok": final_completeness_ok,
            },
            "final_compliance_verification": {
                "compliance_governance_status": compliance_status,
                "signature_governance_status": signature_status,
                "compliance_governance_ok": compliance_ok,
                "signature_governance_ok": signature_ok,
                "final_compliance_ok": final_compliance_ok,
            },
            "final_packaging_verification": {
                "packaging_governance_status": packaging_status,
                "packaging_ready": _safe_dict(packaging.get("latest_packaging_governance")).get("upload_package_readiness", False),
                "final_packaging_ok": final_packaging_ok,
            },
            "final_timing_verification": {
                "deadline_governance_status": deadline_status,
                "timing_readiness_score": _safe_float(deadline.get("timing_readiness_score"), 0.0),
                "deadline_overdue": bool(_safe_dict(deadline.get("latest_deadline_governance")).get("overdue_submission_indicators", {}).get("deadline_overdue")),
                "final_timing_ok": final_timing_ok,
            },
            "final_supervision_verification": {
                "supervision_ok": final_supervision_ok,
                "operator_assignment_readiness": bool(session.get("active_operator_session")) and supervision_ok,
                "operator_session_id": _safe_str(session.get("operator_session_id"), ""),
                "supervision_window_active": supervision_window_active,
                "operator_acknowledged": operator_acknowledged,
            },
            "final_modality_verification": {
                "modality_governance_status": modality_status,
                "selected_modality": selected_modality,
                "physical_submission_required": physical_required,
                "physical_submission_status": physical_status,
                "final_modality_ok": final_modality_ok,
            },
            "final_escalation_authority": final_escalation_authority,
            "final_escalation_authority_reason": final_escalation_authority_reason,
            "unresolved_blocker_indicators": unresolved_blocker_indicators,
            "governance_override_indicators": overrides,
            "final_readiness_rationale": final_readiness_rationale,
            "final_readiness_rationale_history": final_readiness_rationale_history,
            "final_submission_readiness_decision": decision,
            "final_submission_readiness_decision_reason": final_escalation_authority_reason,
            "warnings": warnings,
            "readiness_declaration_status": readiness_status,
            "readiness_declaration_score": readiness_score,
            "operator_session_id": _safe_str(session.get("operator_session_id"), ""),
            "governance_approval_gating": readiness_ok and final_supervision_ok and not unresolved_blocker_count,
        }

    def _records(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = _safe_list(self.lifecycle.list_items(limit=250).get("items", []))
        snapshot = self._component_snapshot()
        records: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not any(
                [
                    bool(_safe_str(item.get("rfq_id"), "")),
                    bool(_safe_str(item.get("title") or item.get("name") or item.get("description"), "")),
                    bool(_safe_dict(item.get("submission_pack"))),
                    bool(_safe_dict(item.get("compliance_artifacts"))),
                    bool(_safe_dict(item.get("returnable_requirements"))),
                    bool(_safe_dict(item.get("signature_requirements"))),
                    bool(_safe_str(item.get("submission_method") or item.get("submission_channel") or item.get("submission_deadline"), "")),
                ]
            ):
                continue
            records.append(self._record(item, snapshot))
        records.sort(key=lambda record: (_safe_str(record.get("generated_at"), ""), _safe_str(record.get("final_readiness_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_final_readiness(self, limit: int = 20) -> Dict[str, Any]:
        records = self._records(limit=limit)
        latest = records[0] if records else {}
        scores = [_safe_float(record.get("final_submission_readiness_score"), 0.0) for record in records]
        decision_counts: Dict[str, int] = {}
        authority_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("final_submission_readiness_decision"), "defer_final_submission")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
            authority = _safe_str(record.get("final_escalation_authority"), "governance_review_board")
            authority_counts[authority] = authority_counts.get(authority, 0) + 1

        if not records:
            status = "not_found"
        elif any(record.get("final_submission_readiness_status") == "NOT_READY_TO_SUBMIT" for record in records):
            status = "blocked" if any(_safe_int(_safe_dict(record.get("unresolved_blocker_indicators")).get("final_completeness_blocker"), 0) or _safe_int(_safe_dict(record.get("unresolved_blocker_indicators")).get("final_compliance_blocker"), 0) for record in records) else "watch"
        else:
            status = "ok"

        return {
            "status": status,
            "generated_at": _now_iso(),
            "final_submission_readiness_status": _safe_str(latest.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT"),
            "final_submission_readiness_score": round(mean(scores), 2) if scores else 0.0,
            "final_submission_ready_count": sum(1 for record in records if record.get("final_submission_readiness_status") == "READY_TO_SUBMIT"),
            "final_submission_not_ready_count": sum(1 for record in records if record.get("final_submission_readiness_status") == "NOT_READY_TO_SUBMIT"),
            "unresolved_blocker_count": sum(1 for record in records if any(_safe_dict(record.get("unresolved_blocker_indicators")).values())),
            "governance_override_count": sum(1 for record in records if any(_safe_dict(record.get("governance_override_indicators")).values())),
            "final_submission_readiness_decision_counts": decision_counts,
            "final_escalation_authority_counts": authority_counts,
            "final_readiness_history": records,
            "latest_final_readiness": latest,
            "final_readiness_rationale_history": _safe_list(latest.get("final_readiness_rationale_history") or []),
            "operator_assignment_readiness_summary": {
                "ready_count": sum(1 for record in records if record.get("final_supervision_verification", {}).get("supervision_ok")),
                "not_ready_count": sum(1 for record in records if not record.get("final_supervision_verification", {}).get("supervision_ok")),
                "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
            },
            "warnings": [
                warning
                for warning in [
                    "final_readiness_warning" if any(record.get("final_submission_readiness_status") == "NOT_READY_TO_SUBMIT" for record in records) else "",
                    "unresolved_blocker_warning" if any(any(_safe_dict(record.get("unresolved_blocker_indicators")).values()) for record in records) else "",
                    "override_warning" if any(any(_safe_dict(record.get("governance_override_indicators")).values()) for record in records) else "",
                ]
                if warning
            ],
        }

    def latest_final_readiness(self) -> Dict[str, Any]:
        response = self.list_final_readiness(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No final submission readiness records have been recorded yet.",
                "final_readiness": {},
            }
        return {
            "status": response.get("status", "ok"),
            "final_submission_readiness_status": response.get("final_submission_readiness_status", "NOT_READY_TO_SUBMIT"),
            "final_submission_readiness_score": response.get("final_submission_readiness_score", 0.0),
            "latest_final_readiness": response.get("latest_final_readiness", {}),
            "final_readiness_history": response.get("final_readiness_history", []),
            "final_readiness_rationale_history": response.get("final_readiness_rationale_history", []),
            "final_submission_readiness_decision_counts": response.get("final_submission_readiness_decision_counts", {}),
            "final_escalation_authority_counts": response.get("final_escalation_authority_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }

    def final_readiness_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_final_readiness(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("final_readiness_history", [])),
            "final_readiness_history": response.get("final_readiness_history", []),
            "final_readiness_rationale_history": response.get("final_readiness_rationale_history", []),
            "final_submission_readiness_decision_counts": response.get("final_submission_readiness_decision_counts", {}),
            "final_escalation_authority_counts": response.get("final_escalation_authority_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }
