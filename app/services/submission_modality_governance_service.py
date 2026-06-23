from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Set

from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.pilot_operator_session_service import PilotOperatorSessionService
from app.services.pilot_readiness_declaration_service import PilotReadinessDeclarationService
from app.services.physical_submission_governance_service import PhysicalSubmissionGovernanceService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"

EMAIL_KEYWORDS = {"email", "e-mail", "mail"}
PORTAL_KEYWORDS = {"portal", "website", "online", "etender", "e-tender", "eprocurement", "e-procurement"}
PHYSICAL_KEYWORDS = {"physical", "courier", "manual", "hand delivery", "tender box"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    return " ".join(_safe_str(value, "").lower().replace("/", " ").replace("-", " ").split())


def _contains_any(text: str, tokens: Set[str]) -> bool:
    return any(token in text for token in tokens)


def _is_email(item: Dict[str, Any]) -> bool:
    blob = _normalize(
        " ".join(
            [
                _safe_str(item.get("submission_method"), ""),
                _safe_str(item.get("submission_channel"), ""),
                _safe_str(item.get("recipient_email"), ""),
                _safe_str(item.get("submission_email"), ""),
                _safe_str(item.get("buyer_email"), ""),
                _safe_str(item.get("submission_notes"), ""),
            ]
        )
    )
    return _contains_any(blob, EMAIL_KEYWORDS) or bool(_safe_str(item.get("recipient_email"), ""))


def _is_portal(item: Dict[str, Any]) -> bool:
    blob = _normalize(
        " ".join(
            [
                _safe_str(item.get("submission_method"), ""),
                _safe_str(item.get("submission_channel"), ""),
                _safe_str(item.get("portal_url"), ""),
                _safe_str(item.get("submission_portal_url"), ""),
                _safe_str(item.get("tender_portal"), ""),
                _safe_str(item.get("submission_notes"), ""),
            ]
        )
    )
    return _contains_any(blob, PORTAL_KEYWORDS) or bool(_safe_str(item.get("portal_url") or item.get("submission_portal_url"), ""))


def _is_physical(item: Dict[str, Any]) -> bool:
    blob = _normalize(
        " ".join(
            [
                _safe_str(item.get("submission_method"), ""),
                _safe_str(item.get("submission_channel"), ""),
                _safe_str(item.get("delivery_instructions"), ""),
                _safe_str(item.get("submission_notes"), ""),
                _safe_str(item.get("title") or item.get("name") or item.get("description"), ""),
            ]
        )
    )
    return _contains_any(blob, PHYSICAL_KEYWORDS)


def _selected_modality(item: Dict[str, Any]) -> str:
    if _is_portal(item):
        return "portal"
    if _is_email(item):
        return "email"
    if _is_physical(item):
        return "physical"
    submission_method = _normalize(item.get("submission_method") or item.get("submission_channel"))
    if "portal" in submission_method:
        return "portal"
    if "email" in submission_method:
        return "email"
    if "physical" in submission_method or "courier" in submission_method:
        return "physical"
    return "unsupported"


def _fallback_modality(selected: str, supported: Set[str]) -> str:
    if selected in supported:
        return selected
    for candidate in ("portal", "email", "physical"):
        if candidate in supported:
            return candidate
    return "unsupported"


def _score(selected: str, supported: Set[str], conflicts: bool, supervision_ok: bool, readiness_ok: bool) -> float:
    values = [
        100.0 if selected != "unsupported" else 0.0,
        100.0 if supported else 0.0,
        100.0 if not conflicts else 55.0,
        100.0 if supervision_ok else 60.0,
        100.0 if readiness_ok else 55.0,
    ]
    return round(mean(values), 2)


class SubmissionModalityGovernanceService:
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
        self.lifecycle = RfqLifecycleService()

    def _latest_session(self) -> Dict[str, Any]:
        response = self.operator_sessions.latest_operator_session()
        return _safe_dict(response.get("operator_session"))

    def _latest_readiness(self) -> Dict[str, Any]:
        response = self.readiness.latest_declaration()
        return response if isinstance(response, dict) and response.get("status") != "not_found" else {}

    def _lifecycle_item(self, rfq_id: str) -> Dict[str, Any]:
        try:
            response = self.lifecycle.get_item(rfq_id)
        except Exception:
            return {}
        return _safe_dict(response.get("item"))

    def _record(self, item: Dict[str, Any], session: Dict[str, Any], readiness: Dict[str, Any]) -> Dict[str, Any]:
        rfq_id = _safe_str(item.get("rfq_id"), "unknown")
        generated_at = _safe_str(item.get("updated_at") or item.get("generated_at") or session.get("generated_at"), _now_iso())
        title = _safe_str(item.get("title") or item.get("name") or item.get("description"), "")
        selected = _selected_modality(item)
        supported = {channel for channel, enabled in {
            "email": _is_email(item),
            "portal": _is_portal(item),
            "physical": _is_physical(item),
        }.items() if enabled}
        physical_decision = self.physical.list_physical_submissions(limit=50)
        physical_latest = _safe_dict(physical_decision.get("latest_physical_submission"))
        physical_required = bool(physical_latest.get("physical_submission_required")) if physical_latest else _is_physical(item)
        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        supervision_window_active = bool(_safe_dict(session.get("supervision_window")).get("active", False))
        operator_ack = bool(_safe_dict(session.get("operator_acknowledgement")).get("acknowledged", False))
        supervision_ok = bool(session.get("active_operator_session")) and supervision_window_active and operator_ack
        readiness_ok = readiness_status == "READY_FOR_CONTROLLED_PILOT" and readiness_score >= 85.0
        conflict_indicators = {
            "selected_modality_missing": selected == "unsupported",
            "mixed_modality_routing": len(supported) > 1,
            "portal_email_conflict": {"email", "portal"}.issubset(supported),
            "physical_with_digital_conflict": "physical" in supported and bool({"email", "portal"} & supported),
            "unsupported_selected_modality": selected not in {"email", "portal", "physical"},
            "submission_method_missing": not _safe_str(item.get("submission_method") or item.get("submission_channel"), ""),
        }
        unsupported_warnings = [
            warning
            for warning in [
                "unsupported_modality_warning" if selected == "unsupported" else "",
                "portal_email_conflict_warning" if conflict_indicators["portal_email_conflict"] else "",
                "mixed_modality_routing_warning" if conflict_indicators["mixed_modality_routing"] else "",
                "physical_with_digital_conflict_warning" if conflict_indicators["physical_with_digital_conflict"] else "",
            ]
            if warning
        ]
        fallback = _fallback_modality(selected, supported)
        selected_ok = selected in supported if supported else selected != "unsupported"
        modality_supervision_required = selected in {"portal", "physical"} or physical_required
        modality_supervision_ok = supervision_ok and (not modality_supervision_required or readiness_ok)
        modality_governance_score = _score(selected, supported, bool(unsupported_warnings), supervision_ok, readiness_ok)
        if selected == "unsupported" or not readiness_ok or not supervision_ok:
            governance_status = "blocked"
            decision = "block_modality"
        elif conflict_indicators["mixed_modality_routing"] or not selected_ok or not modality_supervision_ok:
            governance_status = "watch"
            decision = "watch_modality"
        else:
            governance_status = "ok"
            decision = "approve_modality"
        return {
            "submission_modality_id": f"{rfq_id}:modality",
            "rfq_id": rfq_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "submission_method": _safe_str(item.get("submission_method") or item.get("submission_channel"), "unknown"),
            "selected_modality": selected,
            "fallback_modality": fallback,
            "supported_modalities": sorted(supported),
            "mixed_modality_routing": len(supported) > 1,
            "modality_governance_score": modality_governance_score,
            "modality_governance_status": governance_status,
            "modality_readiness_validation": {
                "readiness_status": readiness_status,
                "readiness_score": readiness_score,
                "readiness_ok": readiness_ok,
                "supervision_ok": supervision_ok,
                "modality_supervision_required": modality_supervision_required,
                "modality_supervision_ok": modality_supervision_ok,
            },
            "modality_conflict_indicators": conflict_indicators,
            "unsupported_modality_warnings": unsupported_warnings,
            "modality_decision": decision,
            "modality_decision_reason": [
                f"selected={selected}",
                f"fallback={fallback}",
                f"supported={','.join(sorted(supported)) or 'none'}",
                f"mixed={len(supported) > 1}",
                f"readiness_ok={readiness_ok}",
                f"supervision_ok={supervision_ok}",
            ],
            "modality_decision_history": [
                {
                    "submission_modality_id": f"{rfq_id}:modality",
                    "decision": decision,
                    "score": modality_governance_score,
                    "generated_at": generated_at,
                }
            ],
            "submission_channel_governance_summary": {
                "email_supported": "email" in supported,
                "portal_supported": "portal" in supported,
                "physical_supported": "physical" in supported,
                "physical_required": physical_required,
                "fallback_modality": fallback,
                "modality_supervision_required": modality_supervision_required,
                "selected_matches_supported": selected_ok,
            },
            "operator_assignment_readiness": supervision_ok and readiness_ok,
            "governance_approval_gating": readiness_ok and supervision_ok,
            "warnings": unsupported_warnings
            + [
                "modality_conflict_warning" if conflict_indicators["mixed_modality_routing"] else "",
                "supervision_required_warning" if modality_supervision_required and not modality_supervision_ok else "",
                "readiness_no_go_warning" if readiness_status == "NO_GO" else "",
            ],
        }

    def _records(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = _safe_list(self.lifecycle.list_items(limit=250).get("items", []))
        session = self._latest_session()
        readiness = self._latest_readiness()
        records: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not (_is_email(item) or _is_portal(item) or _is_physical(item) or _safe_str(item.get("submission_method"), "").strip()):
                continue
            records.append(self._record(item, session, readiness))
        records.sort(key=lambda record: (_safe_str(record.get("generated_at"), ""), _safe_str(record.get("submission_modality_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_submission_modalities(self, limit: int = 20) -> Dict[str, Any]:
        records = self._records(limit=limit)
        latest = records[0] if records else {}
        scores = [_safe_float(record.get("modality_governance_score"), 0.0) for record in records]
        decision_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("modality_decision"), "watch_modality")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        supported_total = {
            "email": sum(1 for record in records if "email" in _safe_list(record.get("supported_modalities"))),
            "portal": sum(1 for record in records if "portal" in _safe_list(record.get("supported_modalities"))),
            "physical": sum(1 for record in records if "physical" in _safe_list(record.get("supported_modalities"))),
        }
        status = "ok"
        if not records:
            status = "not_found"
        elif any(record.get("modality_governance_status") == "blocked" for record in records):
            status = "blocked"
        elif any(record.get("modality_governance_status") == "watch" for record in records):
            status = "watch"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "submission_modality_status": status,
            "modality_governance_score": round(mean(scores), 2) if scores else 0.0,
            "selected_modality": _safe_str(latest.get("selected_modality"), "unsupported"),
            "fallback_modality": _safe_str(latest.get("fallback_modality"), "unsupported"),
            "supported_modality_counts": supported_total,
            "mixed_modality_rfq_count": sum(1 for record in records if record.get("mixed_modality_routing")),
            "unsupported_modality_warning_count": sum(1 for record in records if record.get("unsupported_modality_warnings")),
            "portal_email_conflict_count": sum(1 for record in records if record.get("modality_conflict_indicators", {}).get("portal_email_conflict")),
            "physical_digital_conflict_count": sum(1 for record in records if record.get("modality_conflict_indicators", {}).get("physical_with_digital_conflict")),
            "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
            "operator_assignment_ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
            "submission_channel_governance_summaries": [
                record.get("submission_channel_governance_summary", {})
                for record in records
            ],
            "modality_decision_counts": decision_counts,
            "modality_decision_history": records,
            "latest_submission_modality": latest,
            "warnings": [
                warning
                for warning in [
                    "unsupported_modality_warning" if any(record.get("unsupported_modality_warnings") for record in records) else "",
                    "mixed_modality_warning" if any(record.get("mixed_modality_routing") for record in records) else "",
                    "portal_email_conflict_warning" if any(record.get("modality_conflict_indicators", {}).get("portal_email_conflict") for record in records) else "",
                    "physical_digital_conflict_warning" if any(record.get("modality_conflict_indicators", {}).get("physical_with_digital_conflict") for record in records) else "",
                ]
                if warning
            ],
        }

    def latest_submission_modality(self) -> Dict[str, Any]:
        response = self.list_submission_modalities(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No submission modality governance records have been recorded yet.",
                "submission_modality": {},
            }
        return {
            "status": response.get("status", "ok"),
            "submission_modality_status": response.get("submission_modality_status", "watch"),
            "modality_governance_score": response.get("modality_governance_score", 0.0),
            "selected_modality": response.get("selected_modality", "unsupported"),
            "fallback_modality": response.get("fallback_modality", "unsupported"),
            "latest_submission_modality": response.get("latest_submission_modality", {}),
            "modality_decision_history": response.get("modality_decision_history", []),
            "modality_decision_counts": response.get("modality_decision_counts", {}),
            "submission_channel_governance_summaries": response.get("submission_channel_governance_summaries", []),
            "warnings": response.get("warnings", []),
        }

    def submission_modality_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_submission_modalities(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("modality_decision_history", [])),
            "modality_decision_history": response.get("modality_decision_history", []),
            "modality_decision_counts": response.get("modality_decision_counts", {}),
            "submission_channel_governance_summaries": response.get("submission_channel_governance_summaries", []),
            "warnings": response.get("warnings", []),
        }
