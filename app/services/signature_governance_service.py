from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Set

from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.pilot_operator_session_service import PilotOperatorSessionService
from app.services.pilot_readiness_declaration_service import PilotReadinessDeclarationService
from app.services.physical_submission_governance_service import PhysicalSubmissionGovernanceService
from app.services.submission_modality_governance_service import SubmissionModalityGovernanceService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"

WET_SIGNATURE_KEYWORDS: Set[str] = {
    "wet signature",
    "wet-signature",
    "signed original",
    "signed copy",
    "signature page",
    "signature required",
    "original signature",
}

HANDWRITTEN_KEYWORDS: Set[str] = {
    "handwritten",
    "hand written",
    "hand-written",
    "handwritten declaration",
    "handwritten affidavit",
}

WITNESS_KEYWORDS: Set[str] = {
    "witness",
    "witnessed",
    "witness signature",
    "witnessed signature",
    "witness required",
}

COMMISSIONER_KEYWORDS: Set[str] = {
    "commissioner",
    "commissioner of oaths",
    "commissioned",
    "commissioner required",
}

AFFIDAVIT_KEYWORDS: Set[str] = {
    "affidavit",
    "sworn statement",
    "sworn declaration",
}

ATTESTATION_KEYWORDS: Set[str] = {
    "attestation",
    "manual attestation",
    "attest",
    "attested",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    return " ".join(_safe_str(value, "").lower().replace("/", " ").replace("-", " ").split())


def _contains_any(text: str, tokens: Set[str]) -> bool:
    return any(token in text for token in tokens)


def _keywords_from_item(item: Dict[str, Any]) -> str:
    return _normalize(
        " ".join(
            [
                _safe_str(item.get("rfq_id"), ""),
                _safe_str(item.get("title") or item.get("name") or item.get("description"), ""),
                _safe_str(item.get("description"), ""),
                _safe_str(item.get("submission_notes"), ""),
                _safe_str(item.get("delivery_instructions"), ""),
                _safe_str(item.get("attestation"), ""),
                _safe_str(item.get("affidavit"), ""),
                _safe_str(item.get("witness"), ""),
                _safe_str(item.get("commissioner"), ""),
                _safe_str(item.get("signature_requirements"), ""),
            ]
        )
    )


def _requires_wet_signature(blob: str, item: Dict[str, Any]) -> bool:
    return bool(
        _contains_any(blob, WET_SIGNATURE_KEYWORDS)
        or _safe_dict(item.get("signature_requirements")).get("wet_signature_required")
        or _safe_dict(item.get("signature_requirements")).get("signed_original_required")
    )


def _requires_handwritten(blob: str, item: Dict[str, Any]) -> bool:
    return bool(
        _contains_any(blob, HANDWRITTEN_KEYWORDS)
        or _safe_dict(item.get("signature_requirements")).get("handwritten_declaration_required")
        or _safe_dict(item.get("signature_requirements")).get("handwritten_affidavit_required")
    )


def _requires_witness(blob: str, item: Dict[str, Any]) -> bool:
    witness_count = _safe_int(_safe_dict(item.get("signature_requirements")).get("witness_count"), 0)
    return bool(
        _contains_any(blob, WITNESS_KEYWORDS)
        or witness_count > 0
        or _safe_dict(item.get("signature_requirements")).get("witness_required")
    )


def _requires_commissioner(blob: str, item: Dict[str, Any]) -> bool:
    return bool(
        _contains_any(blob, COMMISSIONER_KEYWORDS)
        or _safe_dict(item.get("signature_requirements")).get("commissioner_required")
        or _safe_dict(item.get("signature_requirements")).get("commissioner_of_oaths_required")
    )


def _requires_affidavit(blob: str, item: Dict[str, Any]) -> bool:
    return bool(_contains_any(blob, AFFIDAVIT_KEYWORDS) or _safe_dict(item.get("signature_requirements")).get("affidavit_required"))


def _requires_manual_attestation(blob: str, item: Dict[str, Any]) -> bool:
    return bool(_contains_any(blob, ATTESTATION_KEYWORDS) or _safe_dict(item.get("signature_requirements")).get("manual_attestation_required"))


def _signature_state(item: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(item.get("signature_status") or item.get("signature_governance") or item.get("attestation_status"))


class SignatureGovernanceService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
    ) -> None:
        cycle_root = cycle_root or PILOT_CYCLE_ROOT
        export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.operator_sessions = PilotOperatorSessionService(cycle_root=cycle_root, export_root=export_root)
        self.readiness = PilotReadinessDeclarationService(cycle_root=cycle_root, export_root=export_root)
        self.modality = SubmissionModalityGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.physical = PhysicalSubmissionGovernanceService(cycle_root=cycle_root, export_root=export_root)
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
        blob = _keywords_from_item(item)
        wet_signature_required = _requires_wet_signature(blob, item)
        handwritten_required = _requires_handwritten(blob, item)
        witness_required = _requires_witness(blob, item)
        commissioner_required = _requires_commissioner(blob, item)
        affidavit_required = _requires_affidavit(blob, item)
        manual_attestation_required = _requires_manual_attestation(blob, item) or wet_signature_required or handwritten_required or witness_required or commissioner_required

        modality = _safe_dict(self.modality.latest_submission_modality())
        physical = _safe_dict(self.physical.latest_physical_submission())
        selected_modality = _safe_str(modality.get("selected_modality"), "unsupported")
        physical_required = bool(physical.get("latest_physical_submission", {}).get("physical_submission_required"))

        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        supervision_window_active = bool(_safe_dict(session.get("supervision_window")).get("active", False))
        operator_ack = bool(_safe_dict(session.get("operator_acknowledgement")).get("acknowledged", False))
        supervision_ok = bool(session.get("active_operator_session")) and supervision_window_active and operator_ack
        readiness_ok = readiness_status == "READY_FOR_CONTROLLED_PILOT" and readiness_score >= 85.0
        signature_supervision_required = any([wet_signature_required, handwritten_required, witness_required, commissioner_required, affidavit_required, manual_attestation_required, physical_required])
        signature_supervision_ok = supervision_ok and readiness_ok and (selected_modality in {"physical", "portal", "email", "unsupported"} or physical_required)

        unsigned_indicators = {
            "wet_signature_missing": wet_signature_required and not bool(_safe_str(item.get("wet_signature") or item.get("signed_by") or item.get("signature"), "")),
            "handwritten_declaration_missing": handwritten_required and not bool(_safe_str(item.get("handwritten_declaration") or item.get("handwritten_note"), "")),
            "witness_missing": witness_required and not bool(_safe_str(item.get("witness") or item.get("witness_name") or item.get("witness_signature"), "")),
            "commissioner_missing": commissioner_required and not bool(_safe_str(item.get("commissioner") or item.get("commissioner_name") or item.get("commissioner_signature"), "")),
            "affidavit_missing": affidavit_required and not bool(_safe_str(item.get("affidavit") or item.get("affidavit_reference"), "")),
            "manual_attestation_missing": manual_attestation_required and not bool(_safe_str(item.get("manual_attestation") or item.get("attestation_reference"), "")),
        }
        human_completion_required_warnings = [
            warning
            for warning in [
                "wet_signature_required_warning" if wet_signature_required else "",
                "handwritten_declaration_required_warning" if handwritten_required else "",
                "witness_required_warning" if witness_required else "",
                "commissioner_required_warning" if commissioner_required else "",
                "affidavit_required_warning" if affidavit_required else "",
                "manual_attestation_required_warning" if manual_attestation_required else "",
            ]
            if warning
        ]
        signature_governance_score = round(
            mean(
                [
                    100.0 if not human_completion_required_warnings else 55.0,
                    100.0 if not any(unsigned_indicators.values()) else 45.0,
                    100.0 if signature_supervision_ok else 55.0,
                    100.0 if readiness_ok else 50.0,
                    100.0 if physical_required or selected_modality in {"physical", "portal", "email"} else 65.0,
                ]
            ),
            2,
        )
        if any(unsigned_indicators.values()) or not readiness_ok or not supervision_ok:
            governance_status = "blocked"
            decision = "block_signature_governance"
        elif human_completion_required_warnings:
            governance_status = "watch"
            decision = "watch_signature_governance"
        else:
            governance_status = "ok"
            decision = "approve_signature_governance"
        return {
            "signature_governance_id": f"{rfq_id}:signature-governance",
            "rfq_id": rfq_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "wet_signature_required": wet_signature_required,
            "handwritten_declaration_required": handwritten_required,
            "witness_required": witness_required,
            "commissioner_required": commissioner_required,
            "affidavit_required": affidavit_required,
            "manual_attestation_required": manual_attestation_required,
            "manual_attestation_routing": {
                "selected_modality": selected_modality,
                "manual_attestation_route_required": manual_attestation_required or physical_required,
                "physical_submission_required": physical_required,
            },
            "signature_completion_supervision": {
                "supervision_ok": supervision_ok,
                "readiness_ok": readiness_ok,
                "signature_supervision_required": signature_supervision_required,
                "signature_supervision_ok": signature_supervision_ok,
            },
            "human_completion_required_warnings": human_completion_required_warnings,
            "unsigned_document_indicators": unsigned_indicators,
            "affidavit_readiness_indicators": {
                "affidavit_required": affidavit_required,
                "affidavit_present": bool(_safe_str(item.get("affidavit") or item.get("affidavit_reference"), "")),
                "commissioner_required": commissioner_required,
                "witness_required": witness_required,
            },
            "signature_governance_score": signature_governance_score,
            "signature_governance_status": governance_status,
            "signature_decision": decision,
            "signature_decision_reason": [
                f"wet_signature_required={wet_signature_required}",
                f"handwritten_declaration_required={handwritten_required}",
                f"witness_required={witness_required}",
                f"commissioner_required={commissioner_required}",
                f"affidavit_required={affidavit_required}",
                f"manual_attestation_required={manual_attestation_required}",
                f"signature_supervision_ok={signature_supervision_ok}",
            ],
            "manual_attestation_history": [
                {
                    "signature_governance_id": f"{rfq_id}:signature-governance",
                    "decision": decision,
                    "score": signature_governance_score,
                    "generated_at": generated_at,
                }
            ],
            "governance_approval_gating": readiness_ok and supervision_ok,
            "operator_assignment_readiness": supervision_ok and readiness_ok,
            "warnings": human_completion_required_warnings
            + [
                "unsigned_document_warning" if any(unsigned_indicators.values()) else "",
                "signature_supervision_warning" if not signature_supervision_ok else "",
                "readiness_no_go_warning" if readiness_status == "NO_GO" else "",
            ],
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
            blob = _keywords_from_item(item)
            if not any(
                [
                    _contains_any(blob, WET_SIGNATURE_KEYWORDS),
                    _contains_any(blob, HANDWRITTEN_KEYWORDS),
                    _contains_any(blob, WITNESS_KEYWORDS),
                    _contains_any(blob, COMMISSIONER_KEYWORDS),
                    _contains_any(blob, AFFIDAVIT_KEYWORDS),
                    _contains_any(blob, ATTESTATION_KEYWORDS),
                    bool(_safe_dict(item.get("signature_requirements"))),
                ]
            ):
                continue
            records.append(self._item(item, session, readiness))
        records.sort(key=lambda record: (_safe_str(record.get("generated_at"), ""), _safe_str(record.get("signature_governance_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_signature_governance(self, limit: int = 20) -> Dict[str, Any]:
        records = self._records(limit=limit)
        latest = records[0] if records else {}
        scores = [_safe_float(record.get("signature_governance_score"), 0.0) for record in records]
        decision_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("signature_decision"), "watch_signature_governance")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        status = "ok"
        if not records:
            status = "not_found"
        elif any(record.get("signature_governance_status") == "blocked" for record in records):
            status = "blocked"
        elif any(record.get("signature_governance_status") == "watch" for record in records):
            status = "watch"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "signature_governance_status": status,
            "signature_governance_score": round(mean(scores), 2) if scores else 0.0,
            "wet_signature_required_count": sum(1 for record in records if record.get("wet_signature_required")),
            "handwritten_declaration_required_count": sum(1 for record in records if record.get("handwritten_declaration_required")),
            "witness_required_count": sum(1 for record in records if record.get("witness_required")),
            "commissioner_required_count": sum(1 for record in records if record.get("commissioner_required")),
            "affidavit_required_count": sum(1 for record in records if record.get("affidavit_required")),
            "manual_attestation_required_count": sum(1 for record in records if record.get("manual_attestation_required")),
            "signature_governance_decision_counts": decision_counts,
            "signature_governance_decision_history": records,
            "latest_signature_governance": latest,
            "operator_assignment_readiness_summary": {
                "ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
                "not_ready_count": sum(1 for record in records if not record.get("operator_assignment_readiness")),
                "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
            },
            "unsigned_document_warning_count": sum(1 for record in records if any(_safe_dict(record.get("unsigned_document_indicators")).values())),
            "human_completion_required_warning_count": sum(1 for record in records if record.get("human_completion_required_warnings")),
            "warnings": [
                warning
                for warning in [
                    "unsigned_document_warning" if any(any(_safe_dict(record.get("unsigned_document_indicators")).values()) for record in records) else "",
                    "human_completion_required_warning" if any(record.get("human_completion_required_warnings") for record in records) else "",
                ]
                if warning
            ],
        }

    def latest_signature_governance(self) -> Dict[str, Any]:
        response = self.list_signature_governance(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No signature governance records have been recorded yet.",
                "signature_governance": {},
            }
        return {
            "status": response.get("status", "ok"),
            "signature_governance_status": response.get("signature_governance_status", "watch"),
            "signature_governance_score": response.get("signature_governance_score", 0.0),
            "latest_signature_governance": response.get("latest_signature_governance", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "signature_governance_decision_history": response.get("signature_governance_decision_history", []),
            "signature_governance_decision_counts": response.get("signature_governance_decision_counts", {}),
            "warnings": response.get("warnings", []),
        }

    def signature_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_signature_governance(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("signature_governance_decision_history", [])),
            "signature_governance_decision_history": response.get("signature_governance_decision_history", []),
            "signature_governance_decision_counts": response.get("signature_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }
