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

ANNEXURE_KEYWORDS: Set[str] = {"annexure", "appendix", "schedule", "attachment", "addendum", "supplement"}
MANDATORY_KEYWORDS: Set[str] = {"mandatory returnable", "compulsory", "required", "must submit", "must be completed"}
PRICING_SCHEDULE_KEYWORDS: Set[str] = {"pricing schedule", "price schedule", "schedule of prices", "boq", "bill of quantities"}
DECLARATION_KEYWORDS: Set[str] = {"declaration", "sbd", "affidavit", "undertaking", "consent"}
TECHNICAL_SCHEDULE_KEYWORDS: Set[str] = {"technical schedule", "technical response", "specification", "method statement", "compliance matrix"}
COMPULSORY_FORM_KEYWORDS: Set[str] = {"compulsory form", "mandatory form", "required form", "form"}
ATTACHMENT_KEYWORDS: Set[str] = {"attachment", "supporting document", "supporting documents", "evidence", "annexure"}
SIGNATURE_KEYWORDS: Set[str] = {"signature", "signed", "sign", "wet signature", "handwritten", "witness", "commissioner"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    return " ".join(_safe_str(value, "").lower().replace("/", " ").replace("-", " ").split())


def _contains_any(text: str, tokens: Set[str]) -> bool:
    return any(token in text for token in tokens)


def _text_blob(item: Dict[str, Any]) -> str:
    parts: List[str] = [
        _safe_str(item.get("rfq_id"), ""),
        _safe_str(item.get("title") or item.get("name") or item.get("description"), ""),
        _safe_str(item.get("description"), ""),
        _safe_str(item.get("submission_notes"), ""),
        _safe_str(item.get("requirements"), ""),
        _safe_str(item.get("returnables"), ""),
        _safe_str(item.get("annexures"), ""),
        _safe_str(item.get("attachments"), ""),
        _safe_str(item.get("forms"), ""),
        _safe_str(item.get("schedule"), ""),
    ]
    for key in ("returnables", "annexures", "attachments", "forms", "schedules", "required_documents", "bid_response", "compliance_documents"):
        value = item.get(key)
        if isinstance(value, dict):
            parts.extend(_safe_str(entry, "") for entry in value.values())
        elif isinstance(value, list):
            parts.extend(_safe_str(entry, "") for entry in value)
        else:
            parts.append(_safe_str(value, ""))
    return _normalize(" ".join(parts))


def _keywords_present(blob: str, keywords: Set[str]) -> bool:
    return _contains_any(blob, keywords)


def _required_from_map(item: Dict[str, Any], key: str) -> bool:
    required_map = _safe_dict(item.get("returnable_requirements"))
    if isinstance(required_map.get(key), dict):
        return bool(required_map.get(key, {}).get("required", True))
    if key in required_map:
        return bool(required_map.get(key))
    explicit = _safe_dict(item.get("required_returnables")).get(key)
    if isinstance(explicit, dict):
        return bool(explicit.get("required", True))
    if key in _safe_dict(item.get("required_returnables")):
        return bool(_safe_dict(item.get("required_returnables")).get(key))
    return False


def _item_document_value(item: Dict[str, Any], key: str) -> str:
    candidates = [
        item.get(f"{key}_document"),
        item.get(f"{key}_path"),
        item.get(f"{key}_file"),
        item.get(f"{key}_reference"),
        item.get(f"{key}_name"),
        _safe_dict(item.get("documents")).get(key),
        _safe_dict(item.get("returnables")).get(key),
        _safe_dict(item.get("attachments")).get(key),
    ]
    for candidate in candidates:
        text = _safe_str(candidate, "")
        if text:
            return text
    return ""


def _item_explicit_present(item: Dict[str, Any], key: str) -> bool:
    explicit = _safe_dict(item.get("returnable_status")).get(key)
    if isinstance(explicit, dict):
        return bool(explicit.get("present") or explicit.get("available") or explicit.get("attached") or explicit.get("uploaded"))
    explicit = _safe_dict(item.get("returnables")).get(key)
    if isinstance(explicit, dict):
        return bool(explicit.get("present") or explicit.get("available") or explicit.get("attached") or explicit.get("uploaded"))
    return bool(_item_document_value(item, key))


def _item_signature_present(item: Dict[str, Any]) -> bool:
    return bool(
        _safe_str(item.get("signed_by") or item.get("signature") or item.get("signature_name") or item.get("attestation") or item.get("declaration_signature"), "")
    )


class ReturnableGovernanceService:
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

    def _record(self, item: Dict[str, Any], session: Dict[str, Any], readiness: Dict[str, Any]) -> Dict[str, Any]:
        rfq_id = _safe_str(item.get("rfq_id"), "unknown")
        generated_at = _safe_str(item.get("updated_at") or item.get("generated_at") or session.get("generated_at"), _now_iso())
        title = _safe_str(item.get("title") or item.get("name") or item.get("description"), "")
        blob = _text_blob(item)
        returnable_status = _safe_dict(item.get("returnable_status"))
        signature_required = _contains_any(blob, SIGNATURE_KEYWORDS) or bool(returnable_status.get("signature_required"))
        returnable_categories = {
            "annexure": _keywords_present(blob, ANNEXURE_KEYWORDS),
            "mandatory_returnable": _keywords_present(blob, MANDATORY_KEYWORDS) or bool(_safe_dict(item.get("returnable_requirements")).get("mandatory_returnable")),
            "pricing_schedule": _keywords_present(blob, PRICING_SCHEDULE_KEYWORDS) or bool(_safe_dict(item.get("returnable_requirements")).get("pricing_schedule")),
            "declaration": _keywords_present(blob, DECLARATION_KEYWORDS) or bool(_safe_dict(item.get("returnable_requirements")).get("declaration")),
            "technical_schedule": _keywords_present(blob, TECHNICAL_SCHEDULE_KEYWORDS) or bool(_safe_dict(item.get("returnable_requirements")).get("technical_schedule")),
            "compulsory_form": _keywords_present(blob, COMPULSORY_FORM_KEYWORDS) or bool(_safe_dict(item.get("returnable_requirements")).get("compulsory_form")),
            "mandatory_attachment": _keywords_present(blob, ATTACHMENT_KEYWORDS) or bool(_safe_dict(item.get("returnable_requirements")).get("mandatory_attachment")),
        }
        selected_categories = [key for key, enabled in returnable_categories.items() if enabled]
        required_total = max(1, len(selected_categories))

        category_statuses: Dict[str, Dict[str, Any]] = {}
        missing_annexure_indicators: Dict[str, bool] = {}
        incomplete_warnings: List[str] = []
        unsigned_returnable_warnings: List[str] = []
        attachments_found = 0
        complete_found = 0

        for key in returnable_categories:
            required = bool(returnable_categories[key] or _required_from_map(item, key))
            present = _item_explicit_present(item, key)
            signed = _item_signature_present(item) if required and key in {"declaration", "compulsory_form", "mandatory_attachment", "annexure"} else True
            complete = present and (signed or not signature_required)
            expiry_warning = False
            category_statuses[key] = {
                "required": required,
                "present": present,
                "signed": signed,
                "complete": complete,
                "expiry_warning": expiry_warning,
                "document_reference": _item_document_value(item, key),
            }
            attachments_found += 1 if present else 0
            complete_found += 1 if complete and required else 0
            missing_annexure_indicators[f"{key}_missing"] = required and not present
            if required and not present:
                incomplete_warnings.append(f"{key}_missing_warning")
            if required and not signed:
                unsigned_returnable_warnings.append(f"{key}_unsigned_warning")

        pricing_schedule_complete = category_statuses["pricing_schedule"]["complete"]
        declaration_complete = category_statuses["declaration"]["complete"]
        technical_schedule_complete = category_statuses["technical_schedule"]["complete"]
        compulsory_form_ready = category_statuses["compulsory_form"]["complete"]
        mandatory_attachment_complete = category_statuses["mandatory_attachment"]["complete"]
        annexure_classification = "annexure_detected" if category_statuses["annexure"]["present"] else "annexure_missing"
        bid_response_complete = all(
            [
                not incomplete_warnings,
                not unsigned_returnable_warnings,
                pricing_schedule_complete,
                declaration_complete,
                technical_schedule_complete,
                compulsory_form_ready,
                mandatory_attachment_complete,
                bool(selected_categories),
            ]
        )

        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        supervision_window_active = bool(_safe_dict(session.get("supervision_window")).get("active", False))
        operator_ack = bool(_safe_dict(session.get("operator_acknowledgement")).get("acknowledged", False))
        supervision_ok = bool(session.get("active_operator_session")) and supervision_window_active and operator_ack
        readiness_ok = readiness_status == "READY_FOR_CONTROLLED_PILOT" and readiness_score >= 85.0
        governance_gate = readiness_ok and supervision_ok

        score_components = [
            100.0 if governance_gate else 50.0,
            100.0 if not incomplete_warnings else 40.0,
            100.0 if not unsigned_returnable_warnings else 40.0,
            100.0 if pricing_schedule_complete else 55.0,
            100.0 if declaration_complete else 55.0,
            100.0 if technical_schedule_complete else 55.0,
            100.0 if compulsory_form_ready else 55.0,
            100.0 if mandatory_attachment_complete else 55.0,
        ]
        bid_response_completeness_score = round(mean(score_components), 2)

        if not governance_gate or incomplete_warnings or unsigned_returnable_warnings:
            governance_status = "blocked"
            decision = "block_returnable_governance"
        elif category_statuses["annexure"]["present"] is False:
            governance_status = "watch"
            decision = "watch_returnable_governance"
        else:
            governance_status = "ok"
            decision = "approve_returnable_governance"

        return {
            "returnable_governance_id": f"{rfq_id}:returnable-governance",
            "rfq_id": rfq_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "annexure_classification": annexure_classification,
            "mandatory_returnable_detection": category_statuses["mandatory_returnable"]["present"],
            "pricing_schedule_completeness": pricing_schedule_complete,
            "declaration_completeness": declaration_complete,
            "technical_schedule_completeness": technical_schedule_complete,
            "compulsory_form_readiness": compulsory_form_ready,
            "mandatory_attachment_completeness": mandatory_attachment_complete,
            "incomplete_returnable_warnings": incomplete_warnings,
            "missing_annexure_indicators": missing_annexure_indicators,
            "unsigned_returnable_warnings": unsigned_returnable_warnings,
            "bid_response_completeness_score": bid_response_completeness_score,
            "returnable_governance_status": governance_status,
            "returnable_governance_decision": decision,
            "returnable_governance_decision_reason": [
                f"readiness_ok={readiness_ok}",
                f"supervision_ok={supervision_ok}",
                f"incomplete_warnings={len(incomplete_warnings)}",
                f"unsigned_returnable_warnings={len(unsigned_returnable_warnings)}",
                f"selected_categories={len(selected_categories)}",
            ],
            "returnable_governance_history": [
                {
                    "returnable_governance_id": f"{rfq_id}:returnable-governance",
                    "decision": decision,
                    "score": bid_response_completeness_score,
                    "generated_at": generated_at,
                }
            ],
            "operator_assignment_readiness": supervision_ok and readiness_ok,
            "governance_approval_gating": governance_gate,
            "warnings": incomplete_warnings
            + unsigned_returnable_warnings
            + [
                "annexure_missing_warning" if category_statuses["annexure"]["present"] is False else "",
                "readiness_no_go_warning" if readiness_status == "NO_GO" else "",
            ],
            "readiness_declaration_status": readiness_status,
            "readiness_declaration_score": readiness_score,
            "operator_session_id": _safe_str(session.get("operator_session_id"), ""),
            "returnable_categories": category_statuses,
            "returnable_governance_summary": {
                "required_count": len(selected_categories),
                "present_count": attachments_found,
                "complete_count": complete_found,
            },
        }

    def _records(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = _safe_list(self.lifecycle.list_items(limit=250).get("items", []))
        session = self._latest_session()
        readiness = self._latest_readiness()
        records: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            blob = _text_blob(item)
            if not any(
                [
                    _contains_any(blob, ANNEXURE_KEYWORDS),
                    _contains_any(blob, MANDATORY_KEYWORDS),
                    _contains_any(blob, PRICING_SCHEDULE_KEYWORDS),
                    _contains_any(blob, DECLARATION_KEYWORDS),
                    _contains_any(blob, TECHNICAL_SCHEDULE_KEYWORDS),
                    _contains_any(blob, COMPULSORY_FORM_KEYWORDS),
                    _contains_any(blob, ATTACHMENT_KEYWORDS),
                    bool(_safe_dict(item.get("returnable_requirements"))),
                    bool(_safe_dict(item.get("returnable_status"))),
                ]
            ):
                continue
            records.append(self._record(item, session, readiness))
        records.sort(key=lambda record: (_safe_str(record.get("generated_at"), ""), _safe_str(record.get("returnable_governance_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_returnable_governance(self, limit: int = 20) -> Dict[str, Any]:
        records = self._records(limit=limit)
        latest = records[0] if records else {}
        scores = [_safe_float(record.get("bid_response_completeness_score"), 0.0) for record in records]
        decision_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("returnable_governance_decision"), "watch_returnable_governance")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        status = "ok"
        if not records:
            status = "not_found"
        elif any(record.get("returnable_governance_status") == "blocked" for record in records):
            status = "blocked"
        elif any(record.get("returnable_governance_status") == "watch" for record in records):
            status = "watch"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "returnable_governance_status": status,
            "bid_response_completeness_score": round(mean(scores), 2) if scores else 0.0,
            "annexure_classification_counts": {
                "annexure_detected": sum(1 for record in records if record.get("annexure_classification") == "annexure_detected"),
                "annexure_missing": sum(1 for record in records if record.get("annexure_classification") == "annexure_missing"),
            },
            "mandatory_returnable_count": sum(1 for record in records if record.get("mandatory_returnable_detection")),
            "pricing_schedule_complete_count": sum(1 for record in records if record.get("pricing_schedule_completeness")),
            "declaration_complete_count": sum(1 for record in records if record.get("declaration_completeness")),
            "technical_schedule_complete_count": sum(1 for record in records if record.get("technical_schedule_completeness")),
            "compulsory_form_ready_count": sum(1 for record in records if record.get("compulsory_form_readiness")),
            "mandatory_attachment_complete_count": sum(1 for record in records if record.get("mandatory_attachment_completeness")),
            "incomplete_returnable_warning_count": sum(1 for record in records if record.get("incomplete_returnable_warnings")),
            "missing_annexure_indicator_count": sum(1 for record in records if any(_safe_dict(record.get("missing_annexure_indicators")).values())),
            "unsigned_returnable_warning_count": sum(1 for record in records if record.get("unsigned_returnable_warnings")),
            "returnable_governance_decision_counts": decision_counts,
            "returnable_governance_history": records,
            "latest_returnable_governance": latest,
            "operator_assignment_readiness_summary": {
                "ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
                "not_ready_count": sum(1 for record in records if not record.get("operator_assignment_readiness")),
                "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
            },
            "warnings": [
                warning
                for warning in [
                    "incomplete_returnable_warning" if any(record.get("incomplete_returnable_warnings") for record in records) else "",
                    "missing_annexure_warning" if any(any(_safe_dict(record.get("missing_annexure_indicators")).values()) for record in records) else "",
                    "unsigned_returnable_warning" if any(record.get("unsigned_returnable_warnings") for record in records) else "",
                ]
                if warning
            ],
        }

    def latest_returnable_governance(self) -> Dict[str, Any]:
        response = self.list_returnable_governance(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No returnable governance records have been recorded yet.",
                "returnable_governance": {},
            }
        return {
            "status": response.get("status", "ok"),
            "returnable_governance_status": response.get("returnable_governance_status", "watch"),
            "bid_response_completeness_score": response.get("bid_response_completeness_score", 0.0),
            "latest_returnable_governance": response.get("latest_returnable_governance", {}),
            "returnable_governance_history": response.get("returnable_governance_history", []),
            "returnable_governance_decision_counts": response.get("returnable_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }

    def returnable_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_returnable_governance(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("returnable_governance_history", [])),
            "returnable_governance_history": response.get("returnable_governance_history", []),
            "returnable_governance_decision_counts": response.get("returnable_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }
