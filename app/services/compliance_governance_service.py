from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

ARTIFACT_PATTERNS: Dict[str, Set[str]] = {
    "tax_clearance": {"tax clearance", "tax compliance", "sars pin", "tax pin", "tax_compliance"},
    "bbbee": {"bbbee", "b-bbee", "bee certificate", "bbee", "specific goals"},
    "cidb": {"cidb", "cidb grading", "cidb certificate"},
    "coida": {"coida", "workmen's compensation", "compensation fund"},
    "nhbrc": {"nhbrc", "nhbrc certificate"},
    "company_registration": {"company registration", "cipc", "ck document", "registration certificate"},
    "bank_letter": {"bank letter", "bank confirmation", "banking letter", "bank statement"},
}

EXPIRY_FIELD_NAMES: Set[str] = {
    "certificate_expiry",
    "expiry_date",
    "expires_on",
    "expiry",
    "valid_until",
    "valid_to",
    "certificate_valid_until",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    return " ".join(_safe_str(value, "").lower().replace("/", " ").replace("-", " ").split())


def _contains_any(text: str, tokens: Set[str]) -> bool:
    return any(token in text for token in tokens)


def _artifact_blob(item: Dict[str, Any]) -> str:
    parts: List[str] = [
        _safe_str(item.get("rfq_id"), ""),
        _safe_str(item.get("title") or item.get("name") or item.get("description"), ""),
        _safe_str(item.get("description"), ""),
        _safe_str(item.get("submission_notes"), ""),
        _safe_str(item.get("document_notes"), ""),
        _safe_str(item.get("certificate_type"), ""),
        _safe_str(item.get("certificate_name"), ""),
        _safe_str(item.get("artifact_type"), ""),
        _safe_str(item.get("artifact_category"), ""),
        _safe_str(item.get("compliance_artifact"), ""),
    ]
    for key in ("compliance_documents", "supporting_documents", "artifact_paths", "required_documents", "certificate_documents"):
        value = item.get(key)
        if isinstance(value, dict):
            parts.extend(_safe_str(entry, "") for entry in value.values())
        elif isinstance(value, list):
            parts.extend(_safe_str(entry, "") for entry in value)
        else:
            parts.append(_safe_str(value, ""))
    return _normalize(" ".join(parts))


def _artifact_present(item: Dict[str, Any], key: str) -> bool:
    normalized = _artifact_blob(item)
    patterns = ARTIFACT_PATTERNS[key]
    if _contains_any(normalized, patterns):
        return True
    explicit_flags = _safe_dict(item.get("compliance_artifacts")).get(key)
    if isinstance(explicit_flags, dict):
        return bool(
            explicit_flags.get("present")
            or explicit_flags.get("available")
            or explicit_flags.get("uploaded")
            or explicit_flags.get("attached")
        )
    return bool(_safe_str(item.get(f"{key}_document") or item.get(f"{key}_path") or item.get(f"{key}_reference"), ""))


def _artifact_expiry_value(item: Dict[str, Any], key: str) -> str:
    candidates = [
        item.get(f"{key}_expiry"),
        item.get(f"{key}_expiry_date"),
        item.get(f"{key}_expires_on"),
        item.get(f"{key}_valid_until"),
        item.get(f"{key}_certificate_expiry"),
        item.get("certificate_expiry"),
        item.get("expiry_date"),
        item.get("expires_on"),
        item.get("valid_until"),
    ]
    for candidate in candidates:
        text = _safe_str(candidate, "")
        if text:
            return text
    return ""


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value, "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _artifact_valid(item: Dict[str, Any], key: str) -> bool:
    explicit = _safe_dict(item.get("compliance_artifacts")).get(key)
    if isinstance(explicit, dict):
        if explicit.get("valid") is False or explicit.get("invalid") is True:
            return False
    if bool(_safe_dict(item.get("compliance_artifacts")).get(f"{key}_invalid")):
        return False
    if bool(item.get(f"{key}_invalid")):
        return False
    expiry_text = _artifact_expiry_value(item, key)
    if not expiry_text:
        return True
    expiry = _parse_iso_datetime(expiry_text)
    if expiry is None:
        return False
    return expiry >= datetime.now(timezone.utc)


def _expiry_warnings(item: Dict[str, Any], key: str) -> List[str]:
    warnings: List[str] = []
    expiry_text = _artifact_expiry_value(item, key)
    if not expiry_text:
        if _artifact_present(item, key):
            warnings.append(f"{key}_expiry_missing_warning")
        return warnings
    expiry = _parse_iso_datetime(expiry_text)
    if expiry is None:
        warnings.append(f"{key}_expiry_invalid_warning")
        return warnings
    now = datetime.now(timezone.utc)
    if expiry < now:
        warnings.append(f"{key}_certificate_expired_warning")
    elif expiry - now <= timedelta(days=30):
        warnings.append(f"{key}_certificate_expiry_warning")
    return warnings


def _requires_artifact(item: Dict[str, Any], key: str) -> bool:
    blob = _artifact_blob(item)
    if _contains_any(blob, ARTIFACT_PATTERNS[key]):
        return True
    required_map = _safe_dict(item.get("compliance_requirements"))
    explicit = required_map.get(key)
    if isinstance(explicit, dict):
        return bool(explicit.get("required", True))
    return bool(explicit) or bool(_safe_dict(item.get("required_documents")).get(key))


class ComplianceGovernanceService:
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

    def _artifact_entry(self, item: Dict[str, Any], session: Dict[str, Any], readiness: Dict[str, Any]) -> Dict[str, Any]:
        rfq_id = _safe_str(item.get("rfq_id"), "unknown")
        generated_at = _safe_str(item.get("updated_at") or item.get("generated_at") or session.get("generated_at"), _now_iso())
        title = _safe_str(item.get("title") or item.get("name") or item.get("description"), "")
        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        supervision_window_active = bool(_safe_dict(session.get("supervision_window")).get("active", False))
        operator_ack = bool(_safe_dict(session.get("operator_acknowledgement")).get("acknowledged", False))
        supervision_ok = bool(session.get("active_operator_session")) and supervision_window_active and operator_ack
        readiness_ok = readiness_status == "READY_FOR_CONTROLLED_PILOT" and readiness_score >= 85.0
        governance_gate = readiness_ok and supervision_ok

        artifact_results: Dict[str, Dict[str, Any]] = {}
        missing_warnings: List[str] = []
        invalid_indicators: Dict[str, bool] = {}
        expiry_warnings: List[str] = []

        for key in ARTIFACT_PATTERNS:
            required = _requires_artifact(item, key)
            present = _artifact_present(item, key)
            valid = _artifact_valid(item, key)
            expiry_value = _artifact_expiry_value(item, key)
            artifact_results[key] = {
                "required": required,
                "present": present,
                "valid": valid,
                "expiry": expiry_value,
                "expiry_warning": False,
            }
            invalid_indicators[f"{key}_invalid"] = bool(required and present and not valid)
            if required and not present:
                missing_warnings.append(f"{key}_missing_warning")
            if present and not valid:
                expiry_warnings.append(f"{key}_invalid_warning")
            warnings = _expiry_warnings(item, key)
            artifact_results[key]["expiry_warning"] = bool(warnings)
            expiry_warnings.extend(warnings)

        valid_required = sum(1 for result in artifact_results.values() if result["required"] and result["present"] and result["valid"])
        required_total = sum(1 for result in artifact_results.values() if result["required"])
        readiness_components = [
            100.0 if readiness_ok else 50.0,
            100.0 if supervision_ok else 60.0,
            100.0 if required_total == 0 or valid_required == required_total else 45.0,
            100.0 if not missing_warnings else 40.0,
            100.0 if not any(invalid_indicators.values()) else 35.0,
            100.0 if not expiry_warnings or all(warning.endswith("_expiry_warning") for warning in expiry_warnings) else 50.0,
        ]
        compliance_readiness_score = round(mean(readiness_components), 2)

        if not governance_gate or any(invalid_indicators.values()) or missing_warnings:
            governance_status = "blocked"
            decision = "block_compliance_governance"
        elif expiry_warnings:
            governance_status = "watch"
            decision = "watch_compliance_governance"
        else:
            governance_status = "ok"
            decision = "approve_compliance_governance"

        return {
            "compliance_artifact_governance_id": f"{rfq_id}:compliance-governance",
            "rfq_id": rfq_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "tax_clearance_required": artifact_results["tax_clearance"]["required"],
            "tax_clearance_present": artifact_results["tax_clearance"]["present"],
            "tax_clearance_valid": artifact_results["tax_clearance"]["valid"],
            "bbbee_required": artifact_results["bbbee"]["required"],
            "bbbee_present": artifact_results["bbbee"]["present"],
            "bbbee_valid": artifact_results["bbbee"]["valid"],
            "cidb_required": artifact_results["cidb"]["required"],
            "cidb_present": artifact_results["cidb"]["present"],
            "cidb_valid": artifact_results["cidb"]["valid"],
            "coida_required": artifact_results["coida"]["required"],
            "coida_present": artifact_results["coida"]["present"],
            "coida_valid": artifact_results["coida"]["valid"],
            "nhbrc_required": artifact_results["nhbrc"]["required"],
            "nhbrc_present": artifact_results["nhbrc"]["present"],
            "nhbrc_valid": artifact_results["nhbrc"]["valid"],
            "company_registration_required": artifact_results["company_registration"]["required"],
            "company_registration_present": artifact_results["company_registration"]["present"],
            "company_registration_valid": artifact_results["company_registration"]["valid"],
            "bank_letter_required": artifact_results["bank_letter"]["required"],
            "bank_letter_present": artifact_results["bank_letter"]["present"],
            "bank_letter_valid": artifact_results["bank_letter"]["valid"],
            "certificate_expiry_governance": {
                key: {
                    "required": artifact_results[key]["required"],
                    "present": artifact_results[key]["present"],
                    "valid": artifact_results[key]["valid"],
                    "expiry": artifact_results[key]["expiry"],
                    "expiry_warning": artifact_results[key]["expiry_warning"],
                }
                for key in ARTIFACT_PATTERNS
            },
            "missing_artifact_warnings": missing_warnings,
            "invalid_artifact_indicators": invalid_indicators,
            "expiry_warnings": expiry_warnings,
            "compliance_readiness_score": compliance_readiness_score,
            "compliance_governance_status": governance_status,
            "compliance_governance_decision": decision,
            "compliance_governance_decision_reason": [
                f"readiness_ok={readiness_ok}",
                f"supervision_ok={supervision_ok}",
                f"required_total={required_total}",
                f"valid_required={valid_required}",
                f"missing_warnings={len(missing_warnings)}",
                f"invalid_indicators={sum(1 for value in invalid_indicators.values() if value)}",
            ],
            "artifact_governance_history": [
                {
                    "compliance_artifact_governance_id": f"{rfq_id}:compliance-governance",
                    "decision": decision,
                    "score": compliance_readiness_score,
                    "generated_at": generated_at,
                }
            ],
            "operator_assignment_readiness": supervision_ok and readiness_ok,
            "governance_approval_gating": governance_gate,
            "warnings": missing_warnings
            + expiry_warnings
            + [
                "governance_gate_warning" if not governance_gate else "",
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
            blob = _artifact_blob(item)
            if not any(
                [
                    _contains_any(blob, ARTIFACT_PATTERNS["tax_clearance"]),
                    _contains_any(blob, ARTIFACT_PATTERNS["bbbee"]),
                    _contains_any(blob, ARTIFACT_PATTERNS["cidb"]),
                    _contains_any(blob, ARTIFACT_PATTERNS["coida"]),
                    _contains_any(blob, ARTIFACT_PATTERNS["nhbrc"]),
                    _contains_any(blob, ARTIFACT_PATTERNS["company_registration"]),
                    _contains_any(blob, ARTIFACT_PATTERNS["bank_letter"]),
                    bool(_safe_dict(item.get("compliance_artifacts"))),
                ]
            ):
                continue
            records.append(self._artifact_entry(item, session, readiness))
        records.sort(key=lambda record: (_safe_str(record.get("generated_at"), ""), _safe_str(record.get("compliance_artifact_governance_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_compliance_governance(self, limit: int = 20) -> Dict[str, Any]:
        records = self._records(limit=limit)
        latest = records[0] if records else {}
        scores = [_safe_float(record.get("compliance_readiness_score"), 0.0) for record in records]
        decision_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("compliance_governance_decision"), "watch_compliance_governance")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        status = "ok"
        if not records:
            status = "not_found"
        elif any(record.get("compliance_governance_status") == "blocked" for record in records):
            status = "blocked"
        elif any(record.get("compliance_governance_status") == "watch" for record in records):
            status = "watch"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "compliance_artifact_governance_status": status,
            "compliance_readiness_score": round(mean(scores), 2) if scores else 0.0,
            "tax_clearance_required_count": sum(1 for record in records if record.get("tax_clearance_required")),
            "bbbee_required_count": sum(1 for record in records if record.get("bbbee_required")),
            "cidb_required_count": sum(1 for record in records if record.get("cidb_required")),
            "coida_required_count": sum(1 for record in records if record.get("coida_required")),
            "nhbrc_required_count": sum(1 for record in records if record.get("nhbrc_required")),
            "company_registration_required_count": sum(1 for record in records if record.get("company_registration_required")),
            "bank_letter_required_count": sum(1 for record in records if record.get("bank_letter_required")),
            "missing_artifact_warning_count": sum(1 for record in records if record.get("missing_artifact_warnings")),
            "invalid_artifact_indicator_count": sum(1 for record in records if any(_safe_dict(record.get("invalid_artifact_indicators")).values())),
            "expiry_warning_count": sum(1 for record in records if record.get("expiry_warnings")),
            "compliance_governance_decision_counts": decision_counts,
            "compliance_governance_decision_history": records,
            "latest_compliance_governance": latest,
            "operator_assignment_readiness_summary": {
                "ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
                "not_ready_count": sum(1 for record in records if not record.get("operator_assignment_readiness")),
                "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
            },
            "certificate_expiry_governance_summary": {
                key: {
                    "required_count": sum(1 for record in records if record.get(f"{key}_required")),
                    "present_count": sum(1 for record in records if record.get(f"{key}_present")),
                    "valid_count": sum(1 for record in records if record.get(f"{key}_valid")),
                }
                for key in ARTIFACT_PATTERNS
            },
            "warnings": [
                warning
                for warning in [
                    "missing_artifact_warning" if any(record.get("missing_artifact_warnings") for record in records) else "",
                    "invalid_artifact_warning" if any(any(_safe_dict(record.get("invalid_artifact_indicators")).values()) for record in records) else "",
                    "expiry_warning" if any(record.get("expiry_warnings") for record in records) else "",
                ]
                if warning
            ],
        }

    def latest_compliance_governance(self) -> Dict[str, Any]:
        response = self.list_compliance_governance(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No compliance artifact governance records have been recorded yet.",
                "compliance_artifact_governance": {},
            }
        return {
            "status": response.get("status", "ok"),
            "compliance_artifact_governance_status": response.get("compliance_artifact_governance_status", "watch"),
            "compliance_readiness_score": response.get("compliance_readiness_score", 0.0),
            "latest_compliance_governance": response.get("latest_compliance_governance", {}),
            "compliance_governance_decision_history": response.get("compliance_governance_decision_history", []),
            "compliance_governance_decision_counts": response.get("compliance_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "certificate_expiry_governance_summary": response.get("certificate_expiry_governance_summary", {}),
            "warnings": response.get("warnings", []),
        }

    def compliance_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_compliance_governance(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("compliance_governance_decision_history", [])),
            "compliance_governance_decision_history": response.get("compliance_governance_decision_history", []),
            "compliance_governance_decision_counts": response.get("compliance_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "certificate_expiry_governance_summary": response.get("certificate_expiry_governance_summary", {}),
            "warnings": response.get("warnings", []),
        }
