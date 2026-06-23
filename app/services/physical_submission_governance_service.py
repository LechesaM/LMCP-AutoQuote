from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.pilot_operator_session_service import PilotOperatorSessionService
from app.services.pilot_readiness_declaration_service import PilotReadinessDeclarationService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"

PHYSICAL_METHOD_KEYWORDS = {
    "physical",
    "physical_delivery",
    "courier",
    "courier_hand_delivery",
    "hand_delivery",
    "manual_delivery",
    "hand delivery",
    "courier hand delivery",
    "tender box",
    "manual",
    "physical delivery",
}

PHYSICAL_CONTENT_KEYWORDS = {
    "physical submission",
    "courier",
    "hand delivery",
    "tender box",
    "sealed envelope",
    "seal",
    "signature",
    "printing",
    "printed copy",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    return " ".join(_safe_str(value, "").lower().replace("/", " ").replace("-", " ").split())


def _contains_any(text: str, tokens: set[str]) -> bool:
    return any(token in text for token in tokens)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value, "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _is_physical_required(item: Dict[str, Any]) -> bool:
    submission_method = _normalize(item.get("submission_method") or item.get("submission_channel") or item.get("bid_submission_method"))
    title_blob = _normalize(
        " ".join(
            [
                _safe_str(item.get("rfq_id"), ""),
                _safe_str(item.get("title") or item.get("name") or item.get("description"), ""),
                _safe_str(item.get("description"), ""),
                _safe_str(item.get("submission_notes"), ""),
                _safe_str(item.get("delivery_instructions"), ""),
            ]
        )
    )
    return _contains_any(submission_method, PHYSICAL_METHOD_KEYWORDS) or _contains_any(title_blob, PHYSICAL_CONTENT_KEYWORDS)


def _physical_classification(item: Dict[str, Any]) -> str:
    method = _normalize(item.get("submission_method") or item.get("submission_channel") or item.get("bid_submission_method"))
    if "courier" in method:
        return "courier_hand_delivery"
    if "hand" in method or "manual" in method:
        return "manual_delivery"
    if "physical" in method:
        return "physical_delivery"
    title_blob = _normalize(_safe_str(item.get("title") or item.get("name") or item.get("description"), ""))
    if _contains_any(title_blob, {"courier", "hand delivery", "physical submission", "tender box"}):
        return "courier_hand_delivery" if "courier" in title_blob else "physical_delivery"
    return "physical_delivery"


def _deadline_warnings(item: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    deadline = _safe_str(item.get("submission_deadline") or item.get("closing_date") or item.get("due_date"), "")
    if not deadline:
        warnings.append("missing_delivery_deadline_warning")
    else:
        parsed = _parse_iso_datetime(deadline)
        if parsed is None:
            warnings.append("delivery_deadline_review_required")
        else:
            now = datetime.now(timezone.utc)
            if parsed < now:
                warnings.append("delivery_deadline_overdue")
            elif parsed - now <= timedelta(hours=24):
                warnings.append("delivery_deadline_due_soon")
    if _safe_str(item.get("current_state"), "").upper() in {"REVIEW_REQUIRED", "FAILED", "READY_FOR_RETRY"}:
        warnings.append("delivery_deadline_at_risk")
    return warnings


def _proof_warnings(item: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    if not _safe_str(item.get("proof_of_delivery") or item.get("pod") or item.get("receipt"), ""):
        warnings.append("missing_pod_evidence_warning")
    if not _safe_str(item.get("chain_of_custody") or item.get("handoff_log") or item.get("submission_chain"), ""):
        warnings.append("missing_chain_of_custody_warning")
    if not _safe_str(item.get("signature_placeholder") or item.get("signature") or item.get("signed_by"), ""):
        warnings.append("missing_signature_placeholder_warning")
    if not _safe_str(item.get("seal_placeholder") or item.get("seal") or item.get("sealed_by"), ""):
        warnings.append("missing_seal_placeholder_warning")
    return warnings


def _pack_ready(item: Dict[str, Any]) -> bool:
    current_state = _safe_str(item.get("current_state"), "").upper()
    return bool(
        current_state in {"QUOTE_PACK_READY", "APPROVAL_READY", "SUBMISSION_READY_MANUAL", "SUBMISSION_READY"}
        or _safe_dict(item.get("submission_pack")).get("ready")
        or _safe_dict(item.get("quote_pack")).get("ready")
    )


def _print_signature_seal_requirements(item: Dict[str, Any]) -> Dict[str, Any]:
    blob = _normalize(
        " ".join(
            [
                _safe_str(item.get("title") or item.get("name") or item.get("description"), ""),
                _safe_str(item.get("submission_notes"), ""),
                _safe_str(item.get("delivery_instructions"), ""),
                _safe_str(item.get("submission_pack"), ""),
            ]
        )
    )
    requires_printing = _contains_any(blob, {"print", "printed", "printing", "hard copy", "paper copy"})
    requires_signature = _contains_any(blob, {"signature", "sign", "signed"})
    requires_sealing = _contains_any(blob, {"seal", "sealed", "envelope", "package"})
    return {
        "requires_printing": requires_printing,
        "requires_signature": requires_signature,
        "requires_sealing": requires_sealing,
        "printing_ready": requires_printing and bool(_safe_str(item.get("printed_copy") or item.get("print_ready"), "")),
        "signature_ready": requires_signature and bool(_safe_str(item.get("signature_placeholder") or item.get("signed_by"), "")),
        "sealing_ready": requires_sealing and bool(_safe_str(item.get("sealed_by") or item.get("seal_placeholder"), "")),
    }


class PhysicalSubmissionGovernanceService:
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
        return response if isinstance(response, dict) and response.get("status") != "not_found" else {}

    def _item(self, item: Dict[str, Any], session: Dict[str, Any], readiness: Dict[str, Any]) -> Dict[str, Any]:
        rfq_id = _safe_str(item.get("rfq_id"), "unknown")
        generated_at = _safe_str(item.get("updated_at") or item.get("generated_at") or session.get("generated_at"), _now_iso())
        title = _safe_str(item.get("title") or item.get("name") or item.get("description"), "")
        submission_method = _normalize(item.get("submission_method") or item.get("submission_channel") or item.get("bid_submission_method") or "physical")
        required = _is_physical_required(item)
        classification = _physical_classification(item)
        pack_ready = _pack_ready(item)
        print_requirements = _print_signature_seal_requirements(item)
        custody_present = bool(_safe_str(item.get("chain_of_custody") or item.get("handoff_log") or item.get("submission_chain"), ""))
        pod_present = bool(_safe_str(item.get("proof_of_delivery") or item.get("pod") or item.get("receipt"), ""))
        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        supervision_window_active = bool(_safe_dict(session.get("supervision_window")).get("active", False))
        operator_ack = bool(_safe_dict(session.get("operator_acknowledgement")).get("acknowledged", False))
        supervision_ready = bool(session.get("active_operator_session")) and supervision_window_active and operator_ack
        governance_gate = readiness_status == "READY_FOR_CONTROLLED_PILOT" and readiness_score >= 85.0 and supervision_ready
        handoff_required = classification in {"courier_hand_delivery", "manual_delivery"}
        handoff_tracking_ok = handoff_required and bool(
            _safe_str(item.get("manual_handoff") or item.get("handoff_reference") or item.get("handoff_log"), "")
        )
        chain_of_custody_ok = custody_present and (handoff_tracking_ok or not handoff_required)
        proof_warnings = _proof_warnings(item)
        deadline_warnings = _deadline_warnings(item)
        missing_proof_warnings = [warning for warning in proof_warnings if warning.startswith("missing_")]
        submission_pack_ready = pack_ready and (not print_requirements["requires_printing"] or print_requirements["printing_ready"]) and (
            not print_requirements["requires_signature"] or print_requirements["signature_ready"]
        ) and (not print_requirements["requires_sealing"] or print_requirements["sealing_ready"])
        physical_submission_ready = required and submission_pack_ready and chain_of_custody_ok and governance_gate and not deadline_warnings
        readiness_score_value = round(
            mean(
                [
                    100.0 if required else 0.0,
                    100.0 if submission_pack_ready else 55.0,
                    100.0 if chain_of_custody_ok else 60.0,
                    100.0 if not missing_proof_warnings else 50.0,
                    100.0 if governance_gate else 40.0,
                    100.0 if not deadline_warnings else 60.0,
                ]
            ),
            2,
        )
        if not required or readiness_status == "NO_GO" or not governance_gate:
            governance_status = "blocked"
            decision = "block_physical_submission"
        elif submission_pack_ready and chain_of_custody_ok and not deadline_warnings:
            governance_status = "ok"
            decision = "approve_physical_submission"
        else:
            governance_status = "watch"
            decision = "watch_physical_submission"
        warnings = [
            warning
            for warning in [
                "physical_submission_required_warning" if required else "",
                "submission_pack_not_ready_warning" if not submission_pack_ready else "",
                "missing_chain_of_custody_warning" if not chain_of_custody_ok else "",
                "governance_gate_warning" if not governance_gate else "",
                "manual_handoff_warning" if handoff_required and not handoff_tracking_ok else "",
                "delivery_deadline_warning" if deadline_warnings else "",
                "missing_pod_warning" if not pod_present else "",
                "readiness_no_go_warning" if readiness_status == "NO_GO" else "",
            ]
            if warning
        ]
        return {
            "physical_submission_id": f"{rfq_id}:physical-submission",
            "rfq_id": rfq_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "submission_method": submission_method,
            "physical_submission_required": required,
            "physical_submission_classification": classification,
            "courier_manual_delivery_routing": {
                "route_type": "courier" if classification == "courier_hand_delivery" else "manual_delivery" if classification == "manual_delivery" else "physical_delivery",
                "courier_required": classification == "courier_hand_delivery",
                "manual_delivery_required": handoff_required,
            },
            "chain_of_custody_tracking": {
                "chain_of_custody_present": custody_present,
                "handoff_tracking_ok": handoff_tracking_ok,
                "pod_expected": True,
                "pod_present": pod_present,
            },
            "pod_evidence_placeholders": {
                "pod_placeholder_required": True,
                "pod_placeholder_present": pod_present,
                "proof_of_delivery_placeholder_present": pod_present,
                "signature_placeholder_present": print_requirements["signature_ready"],
                "seal_placeholder_present": print_requirements["sealing_ready"],
            },
            "submission_pack_readiness": submission_pack_ready,
            "printing_signature_sealing_requirements": print_requirements,
            "manual_handoff_tracking": {
                "manual_handoff_required": handoff_required,
                "manual_handoff_present": handoff_tracking_ok,
                "handoff_reference": _safe_str(item.get("manual_handoff") or item.get("handoff_reference") or item.get("handoff_log"), ""),
            },
            "delivery_deadline_warnings": deadline_warnings,
            "missing_proof_warnings": missing_proof_warnings,
            "physical_submission_readiness_score": readiness_score_value,
            "physical_rfq_governance_status": governance_status,
            "physical_submission_decision": decision,
            "physical_submission_decision_reason": [
                f"required={required}",
                f"classification={classification}",
                f"submission_pack_ready={submission_pack_ready}",
                f"chain_of_custody_ok={chain_of_custody_ok}",
                f"governance_gate={governance_gate}",
                f"readiness_status={readiness_status}",
                f"deadline_warnings={len(deadline_warnings)}",
            ],
            "physical_submission_decision_history": [
                {
                    "physical_submission_id": f"{rfq_id}:physical-submission",
                    "decision": decision,
                    "score": readiness_score_value,
                    "generated_at": generated_at,
                }
            ],
            "governance_approval_gating": governance_gate,
            "operator_assignment_readiness": supervision_ready,
            "operator_session_id": _safe_str(session.get("operator_session_id"), ""),
            "operator_name": _safe_str(session.get("operator_name"), "staging-governance-operator"),
            "readiness_declaration_status": readiness_status,
            "readiness_declaration_score": readiness_score,
            "intake_history_ref": _safe_str(item.get("rfq_id"), ""),
            "warnings": warnings,
        }

    def _records(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = _safe_list(self.lifecycle.list_items(limit=250).get("items", []))
        session = self._latest_session()
        readiness = self._latest_readiness()
        records: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict) or not _is_physical_required(item):
                continue
            records.append(self._item(item, session, readiness))
        records.sort(key=lambda record: (_safe_str(record.get("generated_at"), ""), _safe_str(record.get("physical_submission_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_physical_submissions(self, limit: int = 20) -> Dict[str, Any]:
        records = self._records(limit=limit)
        latest = records[0] if records else {}
        score_values = [_safe_float(record.get("physical_submission_readiness_score"), 0.0) for record in records]
        statuses = [record.get("physical_rfq_governance_status") for record in records]
        if not records:
            status = "not_found"
        elif any(state == "blocked" for state in statuses):
            status = "blocked"
        elif any(state == "watch" for state in statuses):
            status = "watch"
        else:
            status = "ok"
        decision_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("physical_submission_decision"), "watch_physical_submission")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        return {
            "status": status,
            "generated_at": _now_iso(),
            "physical_rfq_governance_status": status,
            "physical_submission_readiness_score": round(mean(score_values), 2) if score_values else 0.0,
            "physical_submission_classification": _safe_str(latest.get("physical_submission_classification"), "physical_delivery"),
            "physical_submission_required_count": sum(1 for record in records if record.get("physical_submission_required")),
            "courier_manual_delivery_count": sum(1 for record in records if record.get("courier_manual_delivery_routing", {}).get("manual_delivery_required")),
            "chain_of_custody_count": sum(1 for record in records if record.get("chain_of_custody_tracking", {}).get("chain_of_custody_present")),
            "pod_evidence_count": sum(1 for record in records if record.get("pod_evidence_placeholders", {}).get("pod_placeholder_present")),
            "submission_pack_ready_count": sum(1 for record in records if record.get("submission_pack_readiness")),
            "manual_handoff_count": sum(1 for record in records if record.get("manual_handoff_tracking", {}).get("manual_handoff_present")),
            "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
            "operator_assignment_ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
            "delivery_deadline_warning_count": sum(1 for record in records if record.get("delivery_deadline_warnings")),
            "missing_proof_warning_count": sum(1 for record in records if record.get("missing_proof_warnings")),
            "physical_submission_decision_counts": decision_counts,
            "physical_submission_warning_indicators": {
                "delivery_deadline_warning": any(record.get("delivery_deadline_warnings") for record in records),
                "missing_proof_warning": any(record.get("missing_proof_warnings") for record in records),
                "manual_handoff_warning": any(
                    record.get("manual_handoff_tracking", {}).get("manual_handoff_required")
                    and not record.get("manual_handoff_tracking", {}).get("manual_handoff_present")
                    for record in records
                ),
                "submission_pack_warning": any(not record.get("submission_pack_readiness") for record in records),
            },
            "physical_submission_decision_history": records,
            "latest_physical_submission": latest,
            "warnings": [
                warning
                for warning in [
                    "delivery_deadline_warning" if any(record.get("delivery_deadline_warnings") for record in records) else "",
                    "missing_proof_warning" if any(record.get("missing_proof_warnings") for record in records) else "",
                    "submission_pack_warning" if any(not record.get("submission_pack_readiness") for record in records) else "",
                ]
                if warning
            ],
        }

    def latest_physical_submission(self) -> Dict[str, Any]:
        response = self.list_physical_submissions(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No physical submission governance records have been recorded yet.",
                "physical_submission": {},
            }
        return {
            "status": response.get("status", "ok"),
            "physical_rfq_governance_status": response.get("physical_rfq_governance_status", "watch"),
            "physical_submission_readiness_score": response.get("physical_submission_readiness_score", 0.0),
            "physical_submission_classification": response.get("physical_submission_classification", "physical_delivery"),
            "latest_physical_submission": response.get("latest_physical_submission", {}),
            "physical_submission_decision_history": response.get("physical_submission_decision_history", []),
            "physical_submission_decision_counts": response.get("physical_submission_decision_counts", {}),
            "physical_submission_warning_indicators": response.get("physical_submission_warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def physical_submission_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_physical_submissions(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("physical_submission_decision_history", [])),
            "physical_submission_decision_history": response.get("physical_submission_decision_history", []),
            "physical_submission_decision_counts": response.get("physical_submission_decision_counts", {}),
            "physical_submission_warning_indicators": response.get("physical_submission_warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
