from __future__ import annotations

from datetime import datetime, timezone
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

PACKAGE_KEYWORDS = {"package", "pack", "submission bundle", "submission package", "upload package", "bid pack"}
ZIP_KEYWORDS = {"zip", ".zip", "compressed", "archive"}
PRINT_PACK_KEYWORDS = {"print pack", "print-ready", "printed copy", "hard copy", "paper copy"}
FOLDER_KEYWORDS = {"folder", "directory", "structure", "path"}
NAMING_KEYWORDS = {"naming convention", "naming", "filename", "file name"}
ATTACHMENT_KEYWORDS = {"attachment", "attachments", "supporting document", "supporting documents", "annexure", "returnable"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    return " ".join(_safe_str(value, "").lower().replace("/", " ").replace("-", " ").split())


def _contains_any(text: str, tokens: set[str]) -> bool:
    return any(token in text for token in tokens)


def _blob(item: Dict[str, Any]) -> str:
    parts: List[str] = [
        _safe_str(item.get("rfq_id"), ""),
        _safe_str(item.get("title") or item.get("name") or item.get("description"), ""),
        _safe_str(item.get("description"), ""),
        _safe_str(item.get("submission_notes"), ""),
        _safe_str(item.get("submission_pack"), ""),
        _safe_str(item.get("package_name"), ""),
        _safe_str(item.get("bundle_name"), ""),
        _safe_str(item.get("zip_path"), ""),
        _safe_str(item.get("print_pack_path"), ""),
        _safe_str(item.get("upload_package_path"), ""),
    ]
    for key in ("submission_pack", "attachments", "returnables", "documents", "bundles", "files", "manifest"):
        value = item.get(key)
        if isinstance(value, dict):
            parts.extend(_safe_str(entry, "") for entry in value.values())
        elif isinstance(value, list):
            parts.extend(_safe_str(entry, "") for entry in value)
        else:
            parts.append(_safe_str(value, ""))
    return _normalize(" ".join(parts))


class PackagingGovernanceService:
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
        blob = _blob(item)
        pack = _safe_dict(item.get("submission_pack"))
        attachments = _safe_list(item.get("attachments") or item.get("documents") or item.get("files") or [])
        has_zip = bool(_safe_str(item.get("zip_path") or pack.get("zip_path") or pack.get("zipPath"), "")) or _contains_any(blob, ZIP_KEYWORDS)
        has_print_pack = bool(_safe_str(item.get("print_pack_path") or pack.get("print_pack_path") or pack.get("printPath"), "")) or _contains_any(blob, PRINT_PACK_KEYWORDS)
        folder_structure_valid = bool(_safe_str(item.get("folder_structure_valid") or pack.get("folder_structure_valid"), "")) or _contains_any(blob, FOLDER_KEYWORDS)
        naming_convention_ok = bool(_safe_str(item.get("naming_convention_ok") or pack.get("naming_convention_ok"), "")) or _contains_any(blob, NAMING_KEYWORDS)
        completeness_flags = {
            "submission_bundle_complete": bool(pack.get("ready") or pack.get("submission_ready") or pack.get("approval_ready")),
            "attachment_bundle_valid": bool(attachments),
            "zip_package_integrity": has_zip,
            "print_pack_ready": has_print_pack,
            "folder_structure_valid": folder_structure_valid,
            "naming_convention_governance": naming_convention_ok,
            "upload_package_ready": bool(_safe_str(item.get("upload_package_path") or pack.get("upload_package_path"), "")) or has_zip,
        }
        attachment_warnings: List[str] = []
        if not completeness_flags["submission_bundle_complete"]:
            attachment_warnings.append("submission_bundle_incomplete_warning")
        if not completeness_flags["attachment_bundle_valid"]:
            attachment_warnings.append("missing_attachment_warning")
        if not completeness_flags["zip_package_integrity"]:
            attachment_warnings.append("malformed_bundle_warning")
        if not completeness_flags["print_pack_ready"]:
            attachment_warnings.append("print_pack_not_ready_warning")
        if not completeness_flags["folder_structure_valid"]:
            attachment_warnings.append("folder_structure_warning")
        if not completeness_flags["naming_convention_governance"]:
            attachment_warnings.append("naming_convention_warning")
        if not completeness_flags["upload_package_ready"]:
            attachment_warnings.append("upload_package_not_ready_warning")

        readiness_status = _safe_str(readiness.get("declaration_status"), "WATCH")
        readiness_score = _safe_float(readiness.get("declaration_score"), 0.0)
        supervision_window_active = bool(_safe_dict(session.get("supervision_window")).get("active", False))
        operator_ack = bool(_safe_dict(session.get("operator_acknowledgement")).get("acknowledged", False))
        supervision_ok = bool(session.get("active_operator_session")) and supervision_window_active and operator_ack
        readiness_ok = readiness_status == "READY_FOR_CONTROLLED_PILOT" and readiness_score >= 85.0
        governance_gate = readiness_ok and supervision_ok

        score_components = [
            100.0 if completeness_flags["submission_bundle_complete"] else 45.0,
            100.0 if completeness_flags["attachment_bundle_valid"] else 40.0,
            100.0 if completeness_flags["zip_package_integrity"] else 40.0,
            100.0 if completeness_flags["print_pack_ready"] else 55.0,
            100.0 if completeness_flags["folder_structure_valid"] else 60.0,
            100.0 if completeness_flags["naming_convention_governance"] else 60.0,
            100.0 if completeness_flags["upload_package_ready"] else 50.0,
            100.0 if governance_gate else 50.0,
        ]
        packaging_readiness_score = round(mean(score_components), 2)
        malformed_bundle_indicators = {
            "zip_package_integrity": not completeness_flags["zip_package_integrity"],
            "folder_structure_invalid": not completeness_flags["folder_structure_valid"],
            "naming_convention_invalid": not completeness_flags["naming_convention_governance"],
        }

        if not governance_gate or attachment_warnings:
            governance_status = "blocked"
            decision = "block_packaging_governance"
        elif not completeness_flags["submission_bundle_complete"] or not completeness_flags["attachment_bundle_valid"]:
            governance_status = "watch"
            decision = "watch_packaging_governance"
        else:
            governance_status = "ok"
            decision = "approve_packaging_governance"

        return {
            "packaging_governance_id": f"{rfq_id}:packaging-governance",
            "rfq_id": rfq_id,
            "generated_at": generated_at,
            "rfq_title": title,
            "submission_bundle_completeness": completeness_flags["submission_bundle_complete"],
            "attachment_bundle_validation": completeness_flags["attachment_bundle_valid"],
            "zip_package_integrity": completeness_flags["zip_package_integrity"],
            "print_pack_readiness": completeness_flags["print_pack_ready"],
            "folder_structure_validation": completeness_flags["folder_structure_valid"],
            "naming_convention_governance": completeness_flags["naming_convention_governance"],
            "upload_package_readiness": completeness_flags["upload_package_ready"],
            "incomplete_package_warnings": attachment_warnings,
            "malformed_bundle_indicators": malformed_bundle_indicators,
            "missing_attachment_warnings": [warning for warning in attachment_warnings if warning == "missing_attachment_warning"],
            "packaging_readiness_score": packaging_readiness_score,
            "packaging_governance_status": governance_status,
            "packaging_governance_decision": decision,
            "packaging_governance_decision_reason": [
                f"readiness_ok={readiness_ok}",
                f"supervision_ok={supervision_ok}",
                f"warnings={len(attachment_warnings)}",
            ],
            "submission_bundle_governance_history": [
                {
                    "packaging_governance_id": f"{rfq_id}:packaging-governance",
                    "decision": decision,
                    "score": packaging_readiness_score,
                    "generated_at": generated_at,
                }
            ],
            "operator_assignment_readiness": supervision_ok and readiness_ok,
            "governance_approval_gating": governance_gate,
            "warnings": attachment_warnings + (["readiness_no_go_warning"] if readiness_status == "NO_GO" else []),
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
            blob = _blob(item)
            if not any(
                [
                    _contains_any(blob, PACKAGE_KEYWORDS),
                    _contains_any(blob, ZIP_KEYWORDS),
                    _contains_any(blob, PRINT_PACK_KEYWORDS),
                    _contains_any(blob, FOLDER_KEYWORDS),
                    _contains_any(blob, NAMING_KEYWORDS),
                    _contains_any(blob, ATTACHMENT_KEYWORDS),
                    bool(_safe_dict(item.get("submission_pack"))),
                    bool(_safe_str(item.get("zip_path") or item.get("print_pack_path") or item.get("upload_package_path"), "")),
                ]
            ):
                continue
            records.append(self._item(item, session, readiness))
        records.sort(key=lambda record: (_safe_str(record.get("generated_at"), ""), _safe_str(record.get("packaging_governance_id"), "")), reverse=True)
        return records[: max(1, limit)]

    def list_packaging_governance(self, limit: int = 20) -> Dict[str, Any]:
        records = self._records(limit=limit)
        latest = records[0] if records else {}
        scores = [_safe_float(record.get("packaging_readiness_score"), 0.0) for record in records]
        decision_counts: Dict[str, int] = {}
        for record in records:
            decision = _safe_str(record.get("packaging_governance_decision"), "watch_packaging_governance")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        status = "ok"
        if not records:
            status = "not_found"
        elif any(record.get("packaging_governance_status") == "blocked" for record in records):
            status = "blocked"
        elif any(record.get("packaging_governance_status") == "watch" for record in records):
            status = "watch"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "packaging_governance_status": status,
            "packaging_readiness_score": round(mean(scores), 2) if scores else 0.0,
            "submission_bundle_complete_count": sum(1 for record in records if record.get("submission_bundle_completeness")),
            "attachment_bundle_valid_count": sum(1 for record in records if record.get("attachment_bundle_validation")),
            "zip_package_integrity_count": sum(1 for record in records if record.get("zip_package_integrity")),
            "print_pack_ready_count": sum(1 for record in records if record.get("print_pack_readiness")),
            "folder_structure_valid_count": sum(1 for record in records if record.get("folder_structure_validation")),
            "naming_convention_count": sum(1 for record in records if record.get("naming_convention_governance")),
            "upload_package_ready_count": sum(1 for record in records if record.get("upload_package_readiness")),
            "incomplete_package_warning_count": sum(1 for record in records if record.get("incomplete_package_warnings")),
            "malformed_bundle_indicator_count": sum(1 for record in records if any(_safe_dict(record.get("malformed_bundle_indicators")).values())),
            "missing_attachment_warning_count": sum(1 for record in records if record.get("missing_attachment_warnings")),
            "packaging_governance_decision_counts": decision_counts,
            "packaging_governance_history": records,
            "latest_packaging_governance": latest,
            "operator_assignment_readiness_summary": {
                "ready_count": sum(1 for record in records if record.get("operator_assignment_readiness")),
                "not_ready_count": sum(1 for record in records if not record.get("operator_assignment_readiness")),
                "governance_approval_gate_count": sum(1 for record in records if record.get("governance_approval_gating")),
            },
            "warnings": [
                warning
                for warning in [
                    "incomplete_package_warning" if any(record.get("incomplete_package_warnings") for record in records) else "",
                    "malformed_bundle_warning" if any(any(_safe_dict(record.get("malformed_bundle_indicators")).values()) for record in records) else "",
                    "missing_attachment_warning" if any(record.get("missing_attachment_warnings") for record in records) else "",
                ]
                if warning
            ],
        }

    def latest_packaging_governance(self) -> Dict[str, Any]:
        response = self.list_packaging_governance(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No packaging governance records have been recorded yet.",
                "packaging_governance": {},
            }
        return {
            "status": response.get("status", "ok"),
            "packaging_governance_status": response.get("packaging_governance_status", "watch"),
            "packaging_readiness_score": response.get("packaging_readiness_score", 0.0),
            "latest_packaging_governance": response.get("latest_packaging_governance", {}),
            "packaging_governance_history": response.get("packaging_governance_history", []),
            "packaging_governance_decision_counts": response.get("packaging_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }

    def packaging_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_packaging_governance(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("packaging_governance_history", [])),
            "packaging_governance_history": response.get("packaging_governance_history", []),
            "packaging_governance_decision_counts": response.get("packaging_governance_decision_counts", {}),
            "operator_assignment_readiness_summary": response.get("operator_assignment_readiness_summary", {}),
            "warnings": response.get("warnings", []),
        }
