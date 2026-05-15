from __future__ import annotations

import html
import hashlib
import csv
import json
import os
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SERVICE_VERSION = "QUOTE_COMPILATION_LOCAL_SAFE_V1"
BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = BASE_DIR / "runtime"
OUTPUT_ROOT = RUNTIME_DIR / "quote_compilation"
RFQ_STATE_FILE = RUNTIME_DIR / "rfq_lifecycle" / "rfqs.json"
MANUAL_COMPLETION_FILENAME = "manual_completion.json"
SUBMISSION_PROOF_FILENAME = "submission_proof.json"
AUDIT_TRAIL_FILENAME = "audit_trail.jsonl"
COMPLIANCE_ARCHIVES_DIRNAME = "archives"
COMPLIANCE_ARCHIVE_MANIFEST_FILENAME = "archive_manifest.json"
COMPLIANCE_ARCHIVE_BUNDLE_FILENAME = "bundle.zip"
COMPLIANCE_ARCHIVE_EXPORTS_DIRNAME = "exports"
COMPLIANCE_ARCHIVE_EVIDENCE_BUNDLE_FILENAME = "evidence_bundle.json"
COMPLIANCE_ARCHIVE_READINESS_CHECKLIST_FILENAME = "readiness_checklist.json"
COMPLIANCE_ARCHIVE_AUDIT_TRAIL_FILENAME = "audit_trail.json"
COMPLIANCE_ARCHIVE_EVIDENCE_SNAPSHOT_FILENAME = "evidence_snapshot.json"
COMPLIANCE_ARCHIVE_PRINTABLE_REPORT_FILENAME = "printable_report.html"

MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_SCAN_FILES_PER_DIR = 2500
MAX_SCAN_DEPTH = 5
DEFAULT_LIMIT = 50
MAX_PACKS_RETURNED = 50
MAX_TEXT_PREVIEW_BYTES = 64 * 1024
DEFAULT_VAT_RATE = 15.0
DEFAULT_MARKUP_PERCENT = 25.0

SOURCE_DIRS: Dict[str, Path] = {
    "monthly_quotes": BASE_DIR / "monthly_quotes",
    "runtime/rfq_lifecycle": RUNTIME_DIR / "rfq_lifecycle",
    "runtime/submission_packs": RUNTIME_DIR / "submission_packs",
    "runtime/quote_packs": RUNTIME_DIR / "quote_packs",
    "runtime/submission_pack": RUNTIME_DIR / "submission_pack",
    "runtime/final_submission_v47_5": RUNTIME_DIR / "final_submission_v47_5",
}

SAFE_DOC_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".docx"}
SENSITIVE_PATH_MARKERS = (
    ".env",
    "secret",
    "credential",
    "password",
    "token",
    "cookie",
    "storage_state",
    "key.pem",
    "private_key",
)

SAFETY_FLAGS: Dict[str, bool] = {
    "local_generation_only": True,
    "no_email_send": True,
    "no_portal_upload": True,
    "no_final_submit": True,
}

PRICING_SAFETY_FLAGS: Dict[str, bool] = {
    "local_only": True,
    "not_submitted": True,
    "not_uploaded": True,
    "not_emailed": True,
}

BINDER_SAFETY_FLAGS: Dict[str, bool] = {
    "local_only": True,
    "not_submitted": True,
    "not_uploaded": True,
    "not_emailed": True,
    "no_final_submit": True,
}

MANUAL_COMPLETION_SAFETY_FLAGS: Dict[str, bool] = {
    "local_only": True,
    "not_submitted": True,
    "not_uploaded": True,
    "not_emailed": True,
    "no_portal_calls": True,
    "no_credentials": True,
    "no_final_submit": True,
}

MANUAL_COMPLETION_LIMITS = {
    "submitted_by": 160,
    "submitted_at": 80,
    "portal_name": 160,
    "portal_reference": 240,
    "notes": 2000,
    "uploaded_file_name": 220,
    "uploaded_file_names_count": 50,
}

SUBMISSION_PROOF_LIMITS = {
    "submitted_by": 160,
    "submission_timestamp": 80,
    "portal_name": 160,
    "portal_reference": 240,
    "proof_notes": 2000,
    "buyer_reference": 240,
    "uploaded_file_name": 220,
    "uploaded_files_count": 50,
    "confirmation_message": 2000,
    "screenshot_notes": 1000,
}

FORBIDDEN_MANUAL_COMPLETION_KEYWORDS = (
    "password",
    "passcode",
    "otp",
    "captcha",
    "credential",
    "credentials",
    "secret",
    "token",
    "pin",
)

AUDIT_TRAIL_REDACTION_KEYS = (
    "password",
    "passcode",
    "otp",
    "captcha",
    "credential",
    "credentials",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "cookie",
    "session",
    "session_id",
    "sessionid",
    "bearer",
    "authorization",
    "csrf",
)

AUDIT_TRAIL_REDACTION_VALUES = (
    "password",
    "passcode",
    "otp",
    "captcha",
    "credential",
    "credentials",
    "secret",
    "token",
    "cookie",
    "session",
    "api key",
    "apikey",
    "bearer",
)

MANUAL_COMPLETION_REQUIRED_FIELDS = (
    "submitted_by",
    "submitted_at",
    "portal_name",
    "portal_reference",
    "notes",
    "uploaded_file_names",
)

SUBMISSION_PROOF_REQUIRED_FIELDS = (
    "submitted_by",
    "submission_timestamp",
    "portal_name",
    "portal_reference",
    "proof_notes",
)

SUBMISSION_PROOF_OPTIONAL_FIELDS = (
    "buyer_reference",
    "uploaded_files",
    "confirmation_message",
    "screenshot_notes",
)

SUBMISSION_PROOF_INTERNAL_FIELDS = (
    "pack_id",
    "saved_at",
    "safety",
    "proof_safety",
)

ALLOWED_OPERATOR_ROLES = ("preparer", "reviewer", "submitter", "admin")
OPERATOR_ACTION_ALLOWED_ROLES: Dict[str, Tuple[str, ...]] = {
    "submission_proof_save": ("submitter", "admin"),
    "submission_proof_load": ("submitter", "admin"),
    "submission_proof_export": ("submitter", "admin"),
    "compliance_archive_create": ("admin",),
    "compliance_archive_zip_export": ("admin",),
}
OPERATOR_ACTION_LABELS: Dict[str, str] = {
    "submission_proof_save": "save manual submission proof",
    "submission_proof_load": "load manual submission proof",
    "submission_proof_export": "export manual submission proof",
    "compliance_archive_create": "create compliance archives",
    "compliance_archive_zip_export": "export compliance archive ZIP files",
}

MANUAL_COMPLETION_REVIEW_FIELDS = (
    "submitted_by",
    "submitted_at",
    "portal_name",
    "portal_reference",
    "notes",
    "saved_by",
    "completed_by",
)

SUBMISSION_PROOF_REVIEW_FIELDS = (
    "submitted_by",
    "submission_timestamp",
    "portal_name",
    "portal_reference",
    "proof_notes",
    "buyer_reference",
    "confirmation_message",
    "screenshot_notes",
)

RETURNABLE_STATUSES = {"missing", "available", "completed", "not_applicable", "needs_review"}
SBD_FORM_NAMES = ("SBD 1", "SBD 4", "SBD 6.1", "SBD 8", "SBD 9")


class QuoteCompilationAccessError(PermissionError):
    pass


@dataclass(frozen=True)
class OperatorContext:
    role: str
    name: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, max_length: int = 500, fallback: str = "") -> str:
    if isinstance(max_length, str) and not fallback:
        fallback = max_length
        max_length = 500
    if value is None:
        return fallback
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if not text:
        return fallback
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        text = _safe_text(item, 500)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _strict_text(value: Any, max_length: int, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required.")
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds the maximum length of {max_length} characters.")
    return text


def _normalize_operator_role(value: Any) -> str:
    return _safe_text(value, 40).lower()


def _operator_audit_payload(operator: OperatorContext) -> Dict[str, str]:
    return {
        "operator_role": operator.role,
        "operator_name": operator.name,
    }


def _with_operator_audit_payload(payload: Optional[Any], operator: Optional[OperatorContext]) -> Dict[str, Any]:
    base = dict(payload) if isinstance(payload, dict) else {}
    if operator:
        base.update(_operator_audit_payload(operator))
    return base


def require_operator_access(action: str, role: Any, name: Any) -> OperatorContext:
    normalized_role = _normalize_operator_role(role)
    operator_name = _safe_text(name, 160)
    if normalized_role not in ALLOWED_OPERATOR_ROLES:
        safe_role = _safe_text(role, 80, "missing")
        allowed = ", ".join(ALLOWED_OPERATOR_ROLES)
        raise QuoteCompilationAccessError(f"Unknown operator role '{safe_role}'. Allowed roles: {allowed}.")
    if not operator_name:
        raise QuoteCompilationAccessError("Operator name is required via X-LMCP-Operator-Name.")
    allowed_roles = OPERATOR_ACTION_ALLOWED_ROLES.get(action, ())
    if normalized_role not in allowed_roles:
        action_label = OPERATOR_ACTION_LABELS.get(action, action.replace("_", " "))
        raise QuoteCompilationAccessError(f"Operator role '{normalized_role}' cannot {action_label}.")
    return OperatorContext(role=normalized_role, name=operator_name)


def _manual_completion_path(workspace: Path) -> Path:
    return workspace / MANUAL_COMPLETION_FILENAME


def _submission_proof_path(workspace: Path) -> Path:
    return workspace / SUBMISSION_PROOF_FILENAME


def _audit_trail_path(workspace: Path) -> Path:
    return workspace / AUDIT_TRAIL_FILENAME


def _pack_audit_workspace(pack_id: str, create: bool = False) -> Optional[Path]:
    if not pack_id:
        return None
    try:
        root = OUTPUT_ROOT.resolve()
        candidate = (OUTPUT_ROOT / pack_id).resolve()
        if root not in candidate.parents and candidate != root:
            return None
        if _contains_sensitive_marker(candidate):
            return None
        if create:
            candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        return None


def _audit_trail_field_is_sensitive(field_name: Any) -> bool:
    lowered = _safe_text(field_name, 120).lower()
    return any(keyword in lowered for keyword in AUDIT_TRAIL_REDACTION_KEYS)


def _audit_trail_value_is_sensitive(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return False
    text = _safe_text(value, 2000).lower()
    return any(keyword in text for keyword in AUDIT_TRAIL_REDACTION_VALUES)


def _sanitize_audit_payload(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "[REDACTED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if _audit_trail_value_is_sensitive(value):
            return "[REDACTED]"
        return _safe_text(value, 2000)
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            if _audit_trail_field_is_sensitive(key) or _audit_trail_value_is_sensitive(item):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize_audit_payload(item, depth + 1)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_audit_payload(item, depth + 1) for item in value[:200]]
    if isinstance(value, tuple):
        return [_sanitize_audit_payload(item, depth + 1) for item in list(value)[:200]]
    return _safe_text(value, 2000)


def _read_pack_audit_trail(workspace: Path) -> Dict[str, Any]:
    path = _audit_trail_path(workspace)
    events: List[Dict[str, Any]] = []
    warning_count = 0

    if not path.exists() or not path.is_file():
        return {
            "status": "ok",
            "pack_id": workspace.name,
            "audit_trail_path": _relative(path),
            "events": events,
            "warning_count": warning_count,
            "count": 0,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {
            "status": "ok",
            "pack_id": workspace.name,
            "audit_trail_path": _relative(path),
            "events": events,
            "warning_count": 1,
            "count": 0,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            warning_count += 1
            continue
        if not isinstance(event, dict):
            warning_count += 1
            continue
        event_id = _safe_text(event.get("event_id"), 120)
        timestamp = _safe_text(event.get("timestamp"), 120)
        event_type = _safe_text(event.get("event_type"), 160)
        pack_id = _safe_text(event.get("pack_id"), 160)
        payload = _sanitize_audit_payload(event.get("payload"))
        if not event_id or not timestamp or not event_type or not pack_id:
            warning_count += 1
            continue
        events.append(
            {
                "event_id": event_id,
                "timestamp": timestamp,
                "pack_id": pack_id,
                "event_type": event_type,
                "payload": payload if payload is not None else {},
            }
        )

    return {
        "status": "ok",
        "pack_id": workspace.name,
        "audit_trail_path": _relative(path),
        "events": events,
        "warning_count": warning_count,
        "count": len(events),
        "read_only": True,
        "timestamp": _now_iso(),
    }


def _audit_event_summary(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    event_type = _safe_text(event.get("event_type"), 120)
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    parts = [event_type.replace("_", " ").strip()] if event_type else []
    reason_code = _safe_text(payload.get("reason_code"), 120)
    status = _safe_text(payload.get("status"), 80)
    blocked_reason = _safe_text(payload.get("blocked_reason"), 200)
    allowed = payload.get("allowed")
    if reason_code:
        parts.append(reason_code.replace("_", " "))
    if status:
        parts.append(status.replace("_", " "))
    if blocked_reason:
        parts.append(blocked_reason)
    elif allowed is True:
        parts.append("allowed")
    elif allowed is False:
        parts.append("blocked")
    return " · ".join(part for part in parts if part)


def _printable_text(value: Any, fallback: str = "") -> str:
    return html.escape(_safe_text(value, fallback), quote=True)


def _printable_bool(value: Any) -> str:
    return "Yes" if bool(value) else "No"


def _printable_status_class(status: Any) -> str:
    text = _safe_text(status, "unknown").lower()
    if text in {"ready_manual_only", "ready_for_manual_submission", "ready"} or "ready" in text:
        return "status-good"
    if text in {"blocked", "manual_completion_missing", "manual_completion_invalid"} or "blocked" in text or "missing" in text:
        return "status-blocked"
    if text in {"locked", "manual_only"} or "locked" in text:
        return "status-locked"
    return "status-unknown"


def _printable_list(items: Any, empty_label: str) -> str:
    values = [
        _printable_text(item)
        for item in (items or [])
        if _safe_text(item, "")
    ]
    if not values:
        return f'<p class="printable-empty">{_printable_text(empty_label)}</p>'
    return "<ul>" + "".join(f"<li>{value}</li>" for value in values) + "</ul>"


def _printable_rows(rows: List[Tuple[str, Any]]) -> str:
    return "".join(
        f"<tr><th>{_printable_text(label)}</th><td>{_printable_text(value)}</td></tr>"
        for label, value in rows
    )


def _printable_metric(label: str, value: Any) -> str:
    return f"""
      <div class="printable-metric">
        <span>{_printable_text(label)}</span>
        <b>{_printable_text(value, "N/A")}</b>
      </div>
    """


def _printable_events_table(events: List[Dict[str, Any]]) -> str:
    if not events:
        return '<p class="printable-empty">No audit events available.</p>'
    rows = []
    for event in events:
        rows.append(
            "<tr>"
            f"<td>{_printable_text(event.get('timestamp'), 'No timestamp')}</td>"
            f"<td><span class=\"printable-event-type\">{_printable_text(event.get('event_type'), 'event')}</span></td>"
            f"<td>{_printable_text(event.get('event_id'), 'event')}</td>"
            f"<td>{_printable_text(_audit_event_summary(event), 'Audit event recorded locally.')}</td>"
            "</tr>"
        )
    return (
        '<table class="printable-table printable-events-table">'
        "<thead><tr><th>Timestamp</th><th>Event</th><th>Event ID</th><th>Summary</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _canonical_json_text(value: Any) -> str:
    return json.dumps(_sanitize_audit_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256_hex(value: Any) -> str:
    return hashlib.sha256(_canonical_json_text(value).encode("utf-8")).hexdigest()


def _evidence_snapshot_path(workspace: Path) -> Path:
    return workspace / "evidence_snapshot.json"


def _compliance_archives_root(workspace: Path) -> Path:
    return workspace / COMPLIANCE_ARCHIVES_DIRNAME


def _compliance_archive_path(workspace: Path, archive_id: str) -> Path:
    return _compliance_archives_root(workspace) / archive_id


def _compliance_archive_exports_root(archive_workspace: Path) -> Path:
    return archive_workspace / COMPLIANCE_ARCHIVE_EXPORTS_DIRNAME


def _compliance_archive_manifest_path(archive_workspace: Path) -> Path:
    return archive_workspace / COMPLIANCE_ARCHIVE_MANIFEST_FILENAME


def _compliance_archive_export_path(archive_workspace: Path, archive_id: str) -> Path:
    exports_root = _compliance_archive_exports_root(archive_workspace)
    exports_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = _safe_text(f"{archive_id}-{timestamp}", 160)
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-") or archive_id
    candidate = exports_root / f"{filename}.zip"
    suffix = 1
    while candidate.exists():
        candidate = exports_root / f"{filename}-{suffix}.zip"
        suffix += 1
    return candidate


def _compliance_archive_file_hash(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def _next_compliance_archive_id(workspace: Path) -> str:
    base = datetime.now(timezone.utc).strftime("archive-%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{base}-{suffix}").strip("-")
    archives_root = _compliance_archives_root(workspace)
    while _compliance_archive_path(workspace, candidate).exists():
        candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{base}-{suffix}-{uuid.uuid4().hex[:4]}").strip("-")
    return candidate


def _compliance_archive_latest_manifest(workspace: Path) -> Optional[Dict[str, Any]]:
    archives_root = _compliance_archives_root(workspace)
    if not archives_root.exists() or not archives_root.is_dir():
        return None
    manifests: List[Dict[str, Any]] = []
    for archive_dir in sorted([path for path in archives_root.iterdir() if path.is_dir()], key=lambda path: _modified_at(path), reverse=True):
        manifest = _read_json(_compliance_archive_manifest_path(archive_dir))
        if isinstance(manifest, dict):
            manifest.setdefault("archive_id", archive_dir.name)
            manifest.setdefault("archive_path", _relative(archive_dir))
            manifests.append(manifest)
    return manifests[0] if manifests else None


def _evidence_snapshot_verification_status(
    workspace: Optional[Path],
    manual_completion_validation: Dict[str, Any],
    audit_trail: Dict[str, Any],
    warnings: List[str],
) -> str:
    if not workspace:
        return "unknown"
    if manual_completion_validation.get("status") in {"missing", "invalid"} or not manual_completion_validation.get("allowed"):
        return "blocked"
    if int(audit_trail.get("warning_count") or 0) > 0 or warnings:
        return "warning"
    return "verified"


def _build_evidence_snapshot_payload(
    pack_id: str,
    rfq_reference: str | None = None,
    *,
    gate: Optional[Dict[str, Any]] = None,
    readiness_checklist: Optional[Dict[str, Any]] = None,
    evidence_bundle: Optional[Dict[str, Any]] = None,
    audit_trail: Optional[Dict[str, Any]] = None,
    manual_completion_validation: Optional[Dict[str, Any]] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    safe_pack_id = _safe_text(pack_id, 220)
    workspace = _safe_quote_pack_dir(safe_pack_id)
    generated_at = _now_iso()

    gate = gate or get_submission_binder_gate(safe_pack_id, rfq_reference)
    manual_completion_validation = manual_completion_validation or (
        _manual_completion_gate(workspace) if workspace else {
            "status": "missing",
            "allowed": False,
            "blocked_reason": "Manual completion record is required before final submission.",
        }
    )
    audit_trail = audit_trail or (
        _read_pack_audit_trail(workspace) if workspace else {
            "status": "ok",
            "pack_id": safe_pack_id,
            "audit_trail_path": _relative(_audit_trail_path(OUTPUT_ROOT / safe_pack_id)),
            "events": [],
            "warning_count": 0,
            "count": 0,
            "read_only": True,
            "timestamp": generated_at,
        }
    )
    readiness_checklist = readiness_checklist or _readiness_checklist_payload(gate, audit_trail, manual_completion_validation)
    evidence_bundle = evidence_bundle or _evidence_bundle_payload(gate, readiness_checklist, manual_completion_validation, audit_trail)
    submission_proof_validation = _submission_proof_gate(workspace) if workspace else {
        "status": "missing",
        "allowed": False,
        "blocked_reason": "Submission proof record has not been saved yet.",
        "submission_proof": None,
    }

    warnings: List[str] = []
    manual_status = _safe_text(manual_completion_validation.get("status"), 40)
    if manual_status == "missing":
        warnings.append("Manual completion record is missing.")
    elif manual_status == "invalid":
        warnings.append(_safe_text(manual_completion_validation.get("blocked_reason"), 260) or "Manual completion record is invalid.")
    audit_warning_count = int(audit_trail.get("warning_count") or 0)
    if audit_warning_count:
        warnings.append(f"Audit trail contains {audit_warning_count} invalid line(s) that were skipped.")
    if not gate.get("can_prepare_submission"):
        warnings.append("Submission binder is not ready for manual submission evidence packaging.")
    if manual_completion_validation.get("allowed") is False and manual_completion_validation.get("status") not in {"missing", "invalid"}:
        warnings.append(_safe_text(manual_completion_validation.get("blocked_reason"), 260))
    if submission_proof_validation.get("status") == "invalid":
        warnings.append(_safe_text(submission_proof_validation.get("blocked_reason"), 260) or "Submission proof record is invalid.")

    warnings = _dedupe_preserve_order([warning for warning in warnings if warning])
    verification_status = _evidence_snapshot_verification_status(workspace, manual_completion_validation, audit_trail, warnings)
    submission_proof_record = submission_proof_validation.get("submission_proof") if submission_proof_validation.get("allowed") else None
    snapshot = {
        "status": verification_status,
        "pack_id": safe_pack_id,
        "generated_at": generated_at,
        "evidence_bundle_hash": _sha256_hex(evidence_bundle),
        "readiness_checklist_hash": _sha256_hex(readiness_checklist),
        "audit_trail_hash": _sha256_hex(audit_trail),
        "manual_completion_hash": _sha256_hex(manual_completion_validation.get("manual_completion")),
        "submission_proof_hash": _sha256_hex(submission_proof_record),
        "submission_proof_status": _safe_text(submission_proof_validation.get("status"), 40),
        "submission_proof_present": bool(submission_proof_validation.get("status") == "ok"),
        "verification_status": verification_status,
        "warnings": warnings,
    }
    if persist and workspace:
        try:
            _write_json(_evidence_snapshot_path(workspace), snapshot)
        except OSError:
            pass
    return snapshot


def _printable_section(title: str, body: str, section_class: str = "") -> str:
    extra_class = f" {section_class}" if section_class else ""
    return f"""
      <section class="printable-section{extra_class}">
        <h2>{_printable_text(title)}</h2>
        {body}
      </section>
    """


def _printable_compliance_report_html(report: Dict[str, Any]) -> str:
    status = _safe_text(report.get("status"), "unknown")
    status_class = _printable_status_class(status)
    generated_at = _printable_text(report.get("generated_at"), "Unknown")
    pack_id = _printable_text(report.get("pack_id"), "Unknown")
    compliance_summary = report.get("compliance_summary") if isinstance(report.get("compliance_summary"), dict) else {}
    readiness_checklist = report.get("readiness_checklist") if isinstance(report.get("readiness_checklist"), dict) else {}
    evidence_bundle = report.get("evidence_bundle") if isinstance(report.get("evidence_bundle"), dict) else {}
    evidence_snapshot = report.get("evidence_snapshot") if isinstance(report.get("evidence_snapshot"), dict) else {}
    submission_proof = report.get("submission_proof_record") if isinstance(report.get("submission_proof_record"), dict) else {}
    audit_summary = report.get("audit_summary") if isinstance(report.get("audit_summary"), dict) else {}
    audit_events = report.get("latest_audit_events") if isinstance(report.get("latest_audit_events"), list) else []

    meta = {
        "lmcp-report-generated-at": report.get("generated_at"),
        "lmcp-report-pack-id": report.get("pack_id"),
        "lmcp-report-status": status,
        "lmcp-report-final-submit-locked": report.get("final_submit_locked"),
        "lmcp-report-automated-submit-disabled": report.get("automated_submit_disabled"),
        "lmcp-report-audit-event-count": report.get("audit_event_count"),
        "lmcp-report-audit-warning-count": report.get("audit_warning_count"),
        "lmcp-report-snapshot-status": evidence_snapshot.get("verification_status"),
        "lmcp-report-snapshot-hash": evidence_snapshot.get("evidence_bundle_hash"),
        "lmcp-report-snapshot-generated-at": evidence_snapshot.get("generated_at"),
        "lmcp-report-proof-status": report.get("submission_proof_present") and "present" or "missing",
        "lmcp-report-proof-hash": evidence_snapshot.get("submission_proof_hash"),
        "lmcp-report-proof-saved-at": submission_proof.get("saved_at"),
    }
    meta_tags = "".join(
        f'<meta name="{_printable_text(key)}" content="{_printable_text(value)}" />'
        for key, value in meta.items()
    )

    checklist_summary = readiness_checklist.get("binder_readiness_summary") if isinstance(readiness_checklist.get("binder_readiness_summary"), dict) else {}
    manual_status = _safe_text(readiness_checklist.get("manual_completion_status") or compliance_summary.get("manual_completion_status"), "missing")
    manual_allowed = bool(readiness_checklist.get("manual_completion_allowed"))
    manual_present = bool(readiness_checklist.get("manual_completion_present"))
    final_submit_locked = bool(readiness_checklist.get("final_submit_locked") if "final_submit_locked" in readiness_checklist else report.get("final_submit_locked", True))
    automated_submit_disabled = bool(readiness_checklist.get("automated_submit_disabled") if "automated_submit_disabled" in readiness_checklist else report.get("automated_submit_disabled", True))

    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    readiness_blockers = readiness_checklist.get("blockers") if isinstance(readiness_checklist.get("blockers"), list) else []
    readiness_warnings = readiness_checklist.get("warnings") if isinstance(readiness_checklist.get("warnings"), list) else []
    bundle_warnings = evidence_bundle.get("bundle_warnings") if isinstance(evidence_bundle.get("bundle_warnings"), list) else []

    evidence_manual = evidence_bundle.get("manual_completion_record") if isinstance(evidence_bundle.get("manual_completion_record"), dict) else None
    submission_proof = report.get("submission_proof_record") if isinstance(report.get("submission_proof_record"), dict) else {}
    proof_present = bool(report.get("submission_proof_record"))
    proof_rows = [
        ("Present", _printable_bool(proof_present)),
        ("Status", report.get("submission_proof_present") and "Present" or "Missing"),
        ("Saved At", _safe_text(submission_proof.get("saved_at"), 80)),
        ("Submitted By", submission_proof.get("submitted_by")),
        ("Submission Timestamp", submission_proof.get("submission_timestamp")),
        ("Portal Name", submission_proof.get("portal_name")),
        ("Portal Reference", submission_proof.get("portal_reference")),
        ("Buyer Reference", submission_proof.get("buyer_reference")),
        ("Uploaded Files", len(submission_proof.get("uploaded_files") or [])),
        ("Confirmation Message", submission_proof.get("confirmation_message")),
        ("Screenshot Notes", submission_proof.get("screenshot_notes")),
        ("Proof Notes", submission_proof.get("proof_notes")),
    ]
    evidence_manual_rows = [
        ("Present", _printable_bool(evidence_manual is not None)),
        ("Final Submit Locked", _printable_bool(evidence_bundle.get("final_submit_locked"))),
        ("Automated Submit Disabled", _printable_bool(evidence_bundle.get("automated_submit_disabled"))),
        ("Audit Events", evidence_bundle.get("audit_event_count", 0)),
        ("Warning Count", evidence_bundle.get("audit_warning_count", 0)),
    ]
    if evidence_manual:
        evidence_manual_rows.extend([
            ("Submitted By", evidence_manual.get("submitted_by")),
            ("Submitted At", evidence_manual.get("submitted_at")),
            ("Portal Name", evidence_manual.get("portal_name")),
            ("Portal Reference", evidence_manual.get("portal_reference")),
            ("Uploaded Files", len(evidence_manual.get("uploaded_file_names") or [])),
        ])

    compliance_section = _printable_section(
        "Compliance Summary",
        """
          <div class="grid-two">
            <div class="panel">
              <table class="printable-table">
                <tbody>
                  {compliance_rows}
                </tbody>
              </table>
            </div>
            <div class="panel">
              <h3>Blockers</h3>
              {blockers_html}
              <h3 style="margin-top:12px;">Warnings</h3>
              {warnings_html}
            </div>
          </div>
        """.format(
            compliance_rows=_printable_rows([
                ("Status", compliance_summary.get("status")),
                ("Can Submit Final", _printable_bool(compliance_summary.get("can_submit_final"))),
                ("Manual Completion Present", _printable_bool(compliance_summary.get("manual_completion_present"))),
                ("Manual Completion Allowed", _printable_bool(compliance_summary.get("manual_completion_allowed"))),
                ("Submission Proof Present", _printable_bool(compliance_summary.get("submission_proof_present"))),
                ("Submission Proof Allowed", _printable_bool(compliance_summary.get("submission_proof_allowed"))),
                ("Final Submit Locked", _printable_bool(compliance_summary.get("final_submit_locked"))),
                ("Automated Submit Disabled", _printable_bool(compliance_summary.get("automated_submit_disabled"))),
                ("Audit Event Count", compliance_summary.get("audit_event_count", 0)),
                ("Audit Warning Count", compliance_summary.get("audit_warning_count", 0)),
            ]),
            blockers_html=_printable_list(blockers, "No overall blockers reported."),
            warnings_html=_printable_list(warnings, "No overall warnings reported."),
        ),
    )

    readiness_section = _printable_section(
        "Readiness Checklist Summary",
        """
          <div class="grid-three">
            <div class="panel">
              <table class="printable-table">
                <tbody>
                  {readiness_rows}
                </tbody>
              </table>
            </div>
            <div class="panel">
              <h3>Binder Readiness Summary</h3>
              <table class="printable-table">
                <tbody>
                  {binder_rows}
                </tbody>
              </table>
            </div>
            <div class="panel">
              <h3>Checklist Blockers</h3>
              {checklist_blockers_html}
              <h3 style="margin-top:12px;">Checklist Warnings</h3>
              {checklist_warnings_html}
            </div>
          </div>
        """.format(
            readiness_rows=_printable_rows([
                ("Readiness Status", readiness_checklist.get("readiness_status")),
                ("Manual Completion Status", manual_status),
                ("Manual Completion Present", _printable_bool(readiness_checklist.get("manual_completion_present"))),
                ("Manual Completion Allowed", _printable_bool(readiness_checklist.get("manual_completion_allowed"))),
                ("Submission Proof Status", readiness_checklist.get("submission_proof_status")),
                ("Submission Proof Present", _printable_bool(readiness_checklist.get("submission_proof_present"))),
                ("Can Submit Final", _printable_bool(readiness_checklist.get("can_submit_final"))),
                ("Final Submit Locked", _printable_bool(final_submit_locked)),
                ("Automated Submit Disabled", _printable_bool(automated_submit_disabled)),
                ("Audit Event Count", readiness_checklist.get("audit_event_count", 0)),
                ("Audit Warning Count", readiness_checklist.get("audit_warning_count", 0)),
            ]),
            binder_rows=_printable_rows([
                ("Status", checklist_summary.get("status")),
                ("Binder Score", checklist_summary.get("binder_score", 0)),
                ("Can Prepare Submission", _printable_bool(checklist_summary.get("can_prepare_submission"))),
                ("Blocker Count", checklist_summary.get("blocker_count", 0)),
                ("Missing Returnable Count", checklist_summary.get("missing_returnable_count", 0)),
                ("Message", checklist_summary.get("message")),
            ]),
            checklist_blockers_html=_printable_list(readiness_checklist.get("blockers"), "No readiness blockers reported."),
            checklist_warnings_html=_printable_list(readiness_checklist.get("warnings"), "No readiness warnings reported."),
        ),
    )

    evidence_section = _printable_section(
        "Evidence Bundle Summary",
        """
          <div class="grid-two">
            <div class="panel">
              <table class="printable-table">
                <tbody>
                  {evidence_rows}
                </tbody>
              </table>
            </div>
            <div class="panel">
              <h3>Bundle Warnings</h3>
              {bundle_warnings_html}
              <h3 style="margin-top:12px;">Evidence Bundle Notes</h3>
              <p>{bundle_notes}</p>
            </div>
          </div>
        """.format(
            evidence_rows=_printable_rows(evidence_manual_rows),
            bundle_warnings_html=_printable_list(evidence_bundle.get("bundle_warnings"), "No bundle warnings reported."),
            bundle_notes=_printable_text(evidence_bundle.get("message"), "Submission evidence bundle is read-only."),
        ),
    )

    proof_section = _printable_section(
        "Submission Proof Capture",
        """
          <div class="grid-two">
            <div class="panel">
              <table class="printable-table">
                <tbody>
                  {proof_rows}
                </tbody>
              </table>
            </div>
            <div class="panel">
              <h3>Proof Notes</h3>
              <p>{proof_notes}</p>
              <h3 style="margin-top:12px;">Proof Status</h3>
              <table class="printable-table">
                <tbody>
                  {proof_status_rows}
                </tbody>
              </table>
            </div>
          </div>
        """.format(
            proof_rows=_printable_rows(proof_rows),
            proof_notes=_printable_text(submission_proof.get("proof_notes"), "No submission proof has been saved yet."),
            proof_status_rows=_printable_rows([
                ("Submission Proof Present", _printable_bool(proof_present)),
                ("Final Submit Locked", _printable_bool(report.get("final_submit_locked"))),
                ("Automated Submit Disabled", _printable_bool(report.get("automated_submit_disabled"))),
                ("Proof Hash", evidence_snapshot.get("submission_proof_hash")),
            ]),
        ),
    )

    snapshot_section = _printable_section(
        "Evidence Verification Snapshot",
        """
          <div class="grid-two">
            <div class="panel">
              <table class="printable-table">
                <tbody>
                  {snapshot_rows}
                </tbody>
              </table>
            </div>
            <div class="panel">
              <h3>Snapshot Warnings</h3>
              {snapshot_warnings_html}
              <h3 style="margin-top:12px;">Snapshot Hashes</h3>
              <table class="printable-table">
                <tbody>
                  {snapshot_hash_rows}
                </tbody>
              </table>
            </div>
          </div>
        """.format(
            snapshot_rows=_printable_rows([
                ("Verification Status", evidence_snapshot.get("verification_status")),
                ("Generated At", evidence_snapshot.get("generated_at")),
                ("Pack ID", evidence_snapshot.get("pack_id")),
            ]),
            snapshot_warnings_html=_printable_list(evidence_snapshot.get("warnings"), "No snapshot warnings reported."),
            snapshot_hash_rows=_printable_rows([
                ("Evidence Bundle Hash", evidence_snapshot.get("evidence_bundle_hash")),
                ("Readiness Checklist Hash", evidence_snapshot.get("readiness_checklist_hash")),
                ("Audit Trail Hash", evidence_snapshot.get("audit_trail_hash")),
                ("Manual Completion Hash", evidence_snapshot.get("manual_completion_hash")),
                ("Submission Proof Hash", evidence_snapshot.get("submission_proof_hash")),
            ]),
        ),
    )

    audit_section = _printable_section(
        "Audit Trail Summary",
        """
          <div class="grid-three">
            <div class="panel">
              <table class="printable-table">
                <tbody>
                  {audit_rows}
                </tbody>
              </table>
            </div>
            <div class="panel">
              <h3>Latest Audit Events</h3>
              {events_table}
            </div>
          </div>
        """.format(
            audit_rows=_printable_rows([
                ("Audit Event Count", audit_summary.get("count", 0)),
                ("Audit Warning Count", audit_summary.get("warning_count", 0)),
                ("Audit Trail Path", audit_summary.get("audit_trail_path")),
                ("Latest Event Summary", audit_summary.get("latest_audit_event_summary")),
            ]),
            events_table=_printable_events_table(audit_events),
        ),
    )

    html_doc = (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        f"{meta_tags}"
        f"<title>LMCP AutoQuote Submission Compliance Report - {pack_id}</title>"
        "<style>"
        ':root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #182635; background: #ffffff; }'
        "* { box-sizing: border-box; }"
        "html, body { margin: 0; padding: 0; background: #ffffff; color: #182635; }"
        "body { font-size: 13px; line-height: 1.45; }"
        ".page { max-width: 1120px; margin: 0 auto; padding: 24px; }"
        ".header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; padding-bottom: 16px; border-bottom: 2px solid #dbe5ef; }"
        ".header h1 { margin: 0; font-size: 24px; line-height: 1.15; }"
        ".header p { margin: 6px 0 0; color: #526476; }"
        ".eyebrow { margin: 0 0 6px; text-transform: uppercase; letter-spacing: .16em; color: #0a8f63; font-size: 10px; font-weight: 800; }"
        ".badge { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 7px 10px; border: 1px solid #cad5e0; background: #f7fafc; color: #243444; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .06em; white-space: nowrap; }"
        ".badge.status-good { border-color: #b7ead7; background: #ecfbf4; color: #147a57; }"
        ".badge.status-blocked { border-color: #f0c2c2; background: #fff2f2; color: #a73b3b; }"
        ".badge.status-locked { border-color: #f2d79b; background: #fff8e8; color: #906700; }"
        ".badge.status-unknown { border-color: #d7dfe7; background: #f4f7fa; color: #526476; }"
        ".header-meta { display: grid; gap: 8px; justify-items: end; text-align: right; }"
        ".header-meta div { color: #526476; font-size: 11px; }"
        ".header-meta b { display: block; margin-top: 3px; color: #182635; font-size: 13px; }"
        ".metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 16px; }"
        ".printable-metric { border: 1px solid #dbe5ef; border-radius: 12px; padding: 10px 12px; background: #fff; }"
        ".printable-metric span { display: block; color: #5a6877; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; }"
        ".printable-metric b { display: block; margin-top: 6px; color: #182635; font-size: 14px; }"
        ".section { margin-top: 18px; border: 1px solid #dbe5ef; border-radius: 14px; padding: 14px; background: #fff; break-inside: avoid; }"
        ".section h2 { margin: 0 0 10px; font-size: 15px; }"
        ".grid-two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }"
        ".grid-three { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }"
        ".panel { border: 1px solid #e4ebf1; border-radius: 12px; padding: 12px; background: #fff; break-inside: avoid; }"
        ".panel h3 { margin: 0 0 8px; font-size: 13px; }"
        ".panel p { margin: 0 0 8px; color: #4f6274; }"
        ".panel ul { margin: 0; padding-left: 18px; color: #243444; }"
        ".panel li { margin: 0 0 6px; }"
        ".printable-empty { margin: 0; color: #667789; font-style: italic; }"
        ".printable-table { width: 100%; border-collapse: collapse; font-size: 12px; }"
        ".printable-table th, .printable-table td { padding: 8px 10px; border-bottom: 1px solid #e6edf3; vertical-align: top; text-align: left; }"
        ".printable-table th { color: #607286; width: 190px; font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }"
        ".printable-table td { color: #182635; }"
        ".printable-events-table th:nth-child(1) { width: 180px; }"
        ".printable-events-table th:nth-child(2) { width: 160px; }"
        ".printable-events-table th:nth-child(3) { width: 180px; }"
        ".printable-event-type { display: inline-flex; align-items: center; border-radius: 999px; padding: 5px 8px; background: #f3f7fb; border: 1px solid #d8e1ea; font-size: 10px; text-transform: uppercase; font-weight: 900; letter-spacing: .04em; }"
        ".notes { margin-top: 10px; color: #5a6877; font-size: 11px; }"
        "@media print { @page { margin: 14mm; } body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } .page { padding: 0; max-width: none; } .section, .panel, .printable-metric, .badge { break-inside: avoid; } }"
        "@media (max-width: 960px) { .header, .grid-two, .grid-three, .metrics { grid-template-columns: 1fr; display: grid; } .header { display: grid; } .header-meta { justify-items: start; text-align: left; } }"
        "</style>"
        "</head>"
        "<body>"
        '<main class="page">'
        '<header class="header">'
        "<div>"
        '<p class="eyebrow">LMCP AutoQuote</p>'
        "<h1>Submission Compliance Report</h1>"
        "<p>Printable, read-only evidence report for manual submission review.</p>"
        "</div>"
        '<div class="header-meta">'
        f'<span class="badge {status_class}">Status: {_printable_text(status, "unknown")}</span>'
        f"<div><span>Pack ID</span><b>{pack_id}</b></div>"
        f"<div><span>Generated</span><b>{generated_at}</b></div>"
        "</div>"
        "</header>"
        f'<section class="metrics">{_printable_metric("Manual Completion", "Present" if manual_present else "Missing")}{_printable_metric("Manual Completion Allowed", _printable_bool(manual_allowed))}{_printable_metric("Final Submit Locked", _printable_bool(final_submit_locked))}{_printable_metric("Automated Submit Disabled", _printable_bool(automated_submit_disabled))}</section>'
        f"{compliance_section}"
        f"{readiness_section}"
        f"{evidence_section}"
        f"{proof_section}"
        f"{snapshot_section}"
        f"{audit_section}"
        '<p class="notes">This report is generated locally from pack evidence only. No portal was contacted, no upload was performed, and final submit remains locked.</p>'
        "</main>"
        "</body>"
        "</html>"
    )
    return html_doc


def build_printable_compliance_report(pack_id: str, rfq_reference: str | None = None) -> Dict[str, Any]:
    safe_pack_id = _safe_text(pack_id, 220)
    workspace = _safe_quote_pack_dir(safe_pack_id)
    generated_at = _now_iso()

    compliance_summary = get_submission_binder_compliance_summary(safe_pack_id, rfq_reference)
    readiness_checklist = get_submission_binder_readiness_checklist(safe_pack_id, rfq_reference)
    evidence_bundle = get_submission_binder_evidence_bundle(safe_pack_id, rfq_reference)
    manual_completion_validation = _manual_completion_gate(workspace) if workspace else {
        "status": "missing",
        "allowed": False,
        "blocked_reason": "Manual completion record is required before final submission.",
    }
    submission_proof_validation = _submission_proof_gate(workspace) if workspace else {
        "status": "missing",
        "allowed": False,
        "blocked_reason": "Submission proof record has not been saved yet.",
    }
    audit_trail = _read_pack_audit_trail(workspace) if workspace else {
        "status": "ok",
        "pack_id": safe_pack_id,
        "audit_trail_path": _relative(_audit_trail_path(OUTPUT_ROOT / safe_pack_id)),
        "events": [],
        "warning_count": 0,
        "count": 0,
        "read_only": True,
        "timestamp": generated_at,
    }
    evidence_snapshot = _build_evidence_snapshot_payload(
        safe_pack_id,
        rfq_reference,
        gate=get_submission_binder_gate(safe_pack_id, rfq_reference),
        readiness_checklist=readiness_checklist,
        evidence_bundle=evidence_bundle,
        audit_trail=audit_trail,
        manual_completion_validation=manual_completion_validation,
        persist=True,
    )

    append_pack_audit_event(
        safe_pack_id,
        "printable_report_generated",
        {
            "status": compliance_summary.get("status"),
            "manual_completion_allowed": bool(compliance_summary.get("manual_completion_allowed")),
            "final_submit_locked": bool(compliance_summary.get("final_submit_locked")),
            "audit_event_count": int(audit_trail.get("count") or 0),
            "audit_warning_count": int(audit_trail.get("warning_count") or 0),
        },
    )

    audit_trail = _read_pack_audit_trail(workspace) if workspace else audit_trail
    latest_events = (audit_trail.get("events") or [])[-10:] if isinstance(audit_trail.get("events"), list) else []
    report = {
        "status": _safe_text(compliance_summary.get("status"), 40) or "unknown",
        "pack_id": safe_pack_id,
        "generated_at": generated_at,
        "final_submit_locked": bool(compliance_summary.get("final_submit_locked", True)),
        "automated_submit_disabled": bool(compliance_summary.get("automated_submit_disabled", True)),
        "manual_completion_present": bool(compliance_summary.get("manual_completion_present")),
        "manual_completion_allowed": bool(compliance_summary.get("manual_completion_allowed")),
        "submission_proof_present": bool(submission_proof_validation.get("status") == "ok"),
        "submission_proof_allowed": bool(submission_proof_validation.get("allowed")),
        "submission_proof_saved_at": _safe_text(submission_proof_validation.get("submission_proof", {}).get("saved_at") if isinstance(submission_proof_validation.get("submission_proof"), dict) else "", 80),
        "submission_status": _safe_text(compliance_summary.get("status"), 40),
        "compliance_summary": compliance_summary,
        "readiness_checklist": readiness_checklist,
        "evidence_bundle": evidence_bundle,
        "evidence_snapshot": evidence_snapshot,
        "manual_completion_record": _sanitize_audit_payload(manual_completion_validation.get("manual_completion")) if isinstance(manual_completion_validation.get("manual_completion"), dict) else None,
        "submission_proof_record": _sanitize_audit_payload(submission_proof_validation.get("submission_proof")) if isinstance(submission_proof_validation.get("submission_proof"), dict) else None,
        "audit_summary": {
            "count": int(audit_trail.get("count") or 0),
            "warning_count": int(audit_trail.get("warning_count") or 0),
            "audit_trail_path": audit_trail.get("audit_trail_path"),
            "latest_audit_event_summary": _audit_event_summary(audit_trail.get("events")[-1]) if isinstance(audit_trail.get("events"), list) and audit_trail.get("events") else "",
        },
        "latest_audit_events": _sanitize_audit_payload(latest_events),
        "blockers": _sanitize_audit_payload(compliance_summary.get("blockers") or []),
        "warnings": _sanitize_audit_payload(compliance_summary.get("warnings") or []),
        "html": "",
        "message": "Printable compliance report is read-only. Manual submission remains locked.",
    }
    report["html"] = _printable_compliance_report_html(report)
    return report


def _readiness_checklist_blockers(gate: Dict[str, Any], manual_completion: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    gate_blockers = [
        _safe_text(item, 260)
        for item in gate.get("blockers") or []
        if _safe_text(item, 260)
    ]
    blockers.extend(gate_blockers)

    missing_returnables = [
        _safe_text(item, 220)
        for item in gate.get("missing_returnables") or []
        if _safe_text(item, 220)
    ]
    blockers.extend(missing_returnables)

    manual_reason = _safe_text(manual_completion.get("blocked_reason"), 500)
    if manual_reason and not manual_completion.get("allowed", False):
        blockers.append(manual_reason)

    if not gate.get("matched_binder"):
        blockers.append("No local submission binder metadata matched this pack.")

    return _dedupe_preserve_order(blockers)


def _readiness_checklist_warnings(
    gate: Dict[str, Any],
    manual_completion: Dict[str, Any],
    audit_trail: Dict[str, Any],
) -> List[str]:
    warnings: List[str] = []
    workspace = _safe_quote_pack_dir(gate.get("pack_id") or "")
    submission_proof_validation = _submission_proof_gate(workspace) if workspace else {
        "status": "missing",
        "allowed": False,
        "blocked_reason": "Submission proof record has not been saved yet.",
    }
    audit_warning_count = int(audit_trail.get("warning_count") or 0)
    if audit_warning_count:
        warnings.append(f"Audit trail contains {audit_warning_count} invalid line(s) that were skipped.")
    if manual_completion.get("status") == "invalid":
        warnings.append(_safe_text(manual_completion.get("blocked_reason"), 260) or "Manual completion record is invalid and should be resaved.")
    if submission_proof_validation.get("status") == "invalid":
        warnings.append(_safe_text(submission_proof_validation.get("blocked_reason"), 260) or "Submission proof record is invalid and should be resaved.")
    if gate.get("can_prepare_submission") and manual_completion.get("allowed") is False:
        warnings.append("Submission binder is ready, but manual completion is still required.")
    if gate.get("can_prepare_submission") is False and gate.get("matched_binder"):
        warnings.append("Binder requires review before manual submission can proceed.")
    return _dedupe_preserve_order([warning for warning in warnings if warning])


def _readiness_checklist_payload(
    gate: Dict[str, Any],
    audit_trail: Dict[str, Any],
    manual_completion: Dict[str, Any],
) -> Dict[str, Any]:
    workspace = _safe_quote_pack_dir(gate.get("pack_id") or "")
    submission_proof_validation = _submission_proof_gate(workspace) if workspace else {
        "status": "missing",
        "allowed": False,
        "blocked_reason": "Submission proof record has not been saved yet.",
        "submission_proof": None,
    }
    latest_event = audit_trail.get("events")[-1] if isinstance(audit_trail.get("events"), list) and audit_trail.get("events") else None
    latest_event_summary = _audit_event_summary(latest_event)
    audit_event_count = int(audit_trail.get("count") or 0)
    manual_completion_present = bool(manual_completion.get("status") and manual_completion.get("status") != "missing")
    manual_completion_allowed = bool(manual_completion.get("allowed"))
    submission_proof_present = bool(submission_proof_validation.get("status") == "ok")
    submission_proof_allowed = bool(submission_proof_validation.get("allowed"))
    submission_proof_saved_at = _safe_text(submission_proof_validation.get("submission_proof", {}).get("saved_at") if isinstance(submission_proof_validation.get("submission_proof"), dict) else "", 80)
    can_submit_final = bool(gate.get("can_prepare_submission") and manual_completion_allowed)
    readiness_status = _submission_gate_readiness_status(gate)
    if manual_completion.get("status") == "invalid":
        readiness_status = "manual_completion_invalid"
    elif manual_completion_allowed and can_submit_final:
        readiness_status = "ready_for_manual_submission"
    elif not manual_completion_present:
        readiness_status = "manual_completion_required"
    elif submission_proof_validation.get("status") == "invalid":
        readiness_status = "submission_proof_invalid"

    binder_summary = {
        "status": _safe_text(gate.get("status"), 80),
        "binder_score": int(gate.get("binder_score") or 0),
        "can_prepare_submission": bool(gate.get("can_prepare_submission")),
        "blocker_count": len(gate.get("blockers") or []),
        "missing_returnable_count": len(gate.get("missing_returnables") or []),
        "message": _safe_text(gate.get("message"), 500),
    }
    final_status = "ready_for_manual_submission" if can_submit_final else "blocked"
    if not manual_completion_allowed:
        final_status = "blocked"
    elif can_submit_final:
        final_status = "ready_for_manual_submission"

    payload = {
        "status": gate.get("status") or "ok",
        "pack_id": gate.get("pack_id"),
        "generated_at": _now_iso(),
        "readiness_status": readiness_status,
        "binder_readiness_summary": binder_summary,
        "manual_completion_required": True,
        "manual_completion_present": manual_completion_present,
        "manual_completion_status": manual_completion.get("status", "missing"),
        "manual_completion_allowed": manual_completion_allowed,
        "manual_completion_blocked_reason": _safe_text(manual_completion.get("blocked_reason"), 500),
        "submission_proof_present": submission_proof_present,
        "submission_proof_status": submission_proof_validation.get("status", "missing"),
        "submission_proof_allowed": submission_proof_allowed,
        "submission_proof_blocked_reason": _safe_text(submission_proof_validation.get("blocked_reason"), 500),
        "submission_proof_saved_at": submission_proof_saved_at,
        "can_submit_final": can_submit_final,
        "final_submit_locked": True,
        "automated_submit_disabled": True,
        "final_status": final_status,
        "blockers": _readiness_checklist_blockers(gate, manual_completion),
        "warnings": _readiness_checklist_warnings(gate, manual_completion, audit_trail),
        "audit_event_count": audit_event_count,
        "audit_warning_count": int(audit_trail.get("warning_count") or 0),
        "latest_audit_event_summary": latest_event_summary,
        "latest_audit_event": _sanitize_audit_payload(latest_event) if latest_event else None,
        "audit_trail_path": audit_trail.get("audit_trail_path"),
        "safety_flags": dict(BINDER_SAFETY_FLAGS),
        "message": _safe_text(gate.get("message"), 500),
    }
    return _sanitize_audit_payload(payload)


def _evidence_bundle_warnings(
    gate: Dict[str, Any],
    readiness_checklist: Dict[str, Any],
    manual_completion_validation: Dict[str, Any],
    audit_trail: Dict[str, Any],
) -> List[str]:
    warnings: List[str] = []
    workspace = _safe_quote_pack_dir(gate.get("pack_id") or "")
    submission_proof_validation = _submission_proof_gate(workspace) if workspace else {
        "status": "missing",
        "allowed": False,
        "blocked_reason": "Submission proof record has not been saved yet.",
    }

    manual_status = _safe_text(manual_completion_validation.get("status"), 40)
    manual_reason = _safe_text(manual_completion_validation.get("blocked_reason"), 260)
    if manual_status == "missing":
        warnings.append("Manual completion record is missing. Final submission remains blocked.")
    elif manual_status == "invalid":
        warnings.append(manual_reason or "Manual completion record is invalid and cannot be used.")

    audit_warning_count = int(audit_trail.get("warning_count") or 0)
    if audit_warning_count:
        warnings.append(f"Audit trail contains {audit_warning_count} invalid line(s) that were skipped.")

    readiness_warnings = readiness_checklist.get("warnings")
    if isinstance(readiness_warnings, list):
        warnings.extend(_safe_text(item, 260) for item in readiness_warnings if _safe_text(item, 260))

    if submission_proof_validation.get("status") == "invalid":
        warnings.append(_safe_text(submission_proof_validation.get("blocked_reason"), 260) or "Submission proof record is invalid and should be resaved.")

    if not gate.get("can_prepare_submission"):
        warnings.append("Submission binder is not ready for manual completion evidence packaging.")

    return _dedupe_preserve_order(warnings)


def _evidence_bundle_payload(
    gate: Dict[str, Any],
    readiness_checklist: Dict[str, Any],
    manual_completion_validation: Dict[str, Any],
    audit_trail: Dict[str, Any],
    evidence_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    audit_events = audit_trail.get("events") if isinstance(audit_trail.get("events"), list) else []
    latest_audit_event = audit_events[-1] if audit_events else None
    submission_proof_validation = _submission_proof_gate(_safe_quote_pack_dir(gate.get("pack_id") or "")) if _safe_quote_pack_dir(gate.get("pack_id") or "") else {
        "status": "missing",
        "allowed": False,
        "blocked_reason": "Submission proof record has not been saved yet.",
        "submission_proof": None,
    }
    manual_completion_record = (
        _sanitize_audit_payload(manual_completion_validation.get("manual_completion"))
        if manual_completion_validation.get("allowed") and isinstance(manual_completion_validation.get("manual_completion"), dict)
        else None
    )
    submission_proof_record = (
        _sanitize_audit_payload(submission_proof_validation.get("submission_proof"))
        if submission_proof_validation.get("allowed") and isinstance(submission_proof_validation.get("submission_proof"), dict)
        else None
    )
    bundle_warnings = _evidence_bundle_warnings(gate, readiness_checklist, manual_completion_validation, audit_trail)
    if submission_proof_validation.get("status") == "invalid":
        bundle_warnings.append(_safe_text(submission_proof_validation.get("blocked_reason"), 260) or "Submission proof record is invalid.")
    bundle = {
        "status": gate.get("status") or "ok",
        "pack_id": gate.get("pack_id"),
        "generated_at": _now_iso(),
        "submission_gate_state": _sanitize_audit_payload(gate),
        "readiness_checklist": _sanitize_audit_payload(readiness_checklist),
        "manual_completion_record": manual_completion_record,
        "submission_proof_record": submission_proof_record,
        "submission_proof_status": _safe_text(submission_proof_validation.get("status"), 40),
        "submission_proof_present": bool(submission_proof_validation.get("status") == "ok"),
        "submission_proof_saved_at": _safe_text(submission_proof_record.get("saved_at") if isinstance(submission_proof_record, dict) else "", 80),
        "audit_trail": _sanitize_audit_payload(audit_events),
        "audit_event_count": len(audit_events),
        "audit_warning_count": int(audit_trail.get("warning_count") or 0),
        "bundle_warnings": bundle_warnings,
        "final_submit_locked": True,
        "automated_submit_disabled": True,
        "latest_audit_event_summary": _audit_event_summary(latest_audit_event),
        "latest_audit_event": _sanitize_audit_payload(latest_audit_event) if latest_audit_event else None,
        "safety_flags": dict(BINDER_SAFETY_FLAGS),
        "message": "Submission evidence bundle is read-only. Manual submission only.",
    }
    evidence_snapshot = evidence_snapshot or _build_evidence_snapshot_payload(
        gate.get("pack_id") or _safe_text(gate.get("pack_id"), 220),
        gate.get("rfq_reference"),
        gate=gate,
        readiness_checklist=readiness_checklist,
        evidence_bundle=bundle,
        audit_trail=audit_trail,
        manual_completion_validation=manual_completion_validation,
        persist=True,
    )
    bundle["evidence_snapshot_hash"] = _safe_text(evidence_snapshot.get("evidence_bundle_hash"), 80)
    bundle["evidence_snapshot_verification_status"] = _safe_text(evidence_snapshot.get("verification_status"), 40)
    bundle["evidence_snapshot_generated_at"] = _safe_text(evidence_snapshot.get("generated_at"), 80)
    bundle["submission_proof_hash"] = _safe_text(evidence_snapshot.get("submission_proof_hash"), 80)
    return _sanitize_audit_payload(bundle)


def get_submission_binder_readiness_checklist(
    pack_id: str,
    rfq_reference: str | None = None,
) -> Dict[str, Any]:
    gate = get_submission_binder_gate(pack_id, rfq_reference)
    workspace = _safe_quote_pack_dir(gate.get("pack_id") or pack_id)
    if not workspace:
        return _sanitize_audit_payload(
            {
                "status": "not_found",
                "pack_id": _safe_text(pack_id, 220),
                "generated_at": _now_iso(),
                "readiness_status": "binder_not_found",
                "binder_readiness_summary": {
                    "status": "not_found",
                    "binder_score": 0,
                    "can_prepare_submission": False,
                    "blocker_count": 1,
                    "missing_returnable_count": 0,
                    "message": "No local quote compilation pack matched the requested pack_id.",
                },
                "manual_completion_required": True,
                "manual_completion_present": False,
                "manual_completion_status": "missing",
                "manual_completion_allowed": False,
                "manual_completion_blocked_reason": "Manual completion record is required before final submission.",
                "can_submit_final": False,
                "final_submit_locked": True,
                "automated_submit_disabled": True,
                "final_status": "blocked",
                "blockers": ["No local quote compilation pack matched the requested pack_id."],
                "warnings": [],
                "audit_event_count": 0,
                "audit_warning_count": 0,
                "latest_audit_event_summary": "",
                "latest_audit_event": None,
                "audit_trail_path": _relative(_audit_trail_path(OUTPUT_ROOT / _safe_text(pack_id, 160))),
                "safety_flags": dict(BINDER_SAFETY_FLAGS),
                "message": "No local quote compilation pack matched the requested pack_id.",
            }
        )

    manual_completion = _manual_completion_gate(workspace)
    audit_trail = _read_pack_audit_trail(workspace)
    checklist = _readiness_checklist_payload(gate, audit_trail, manual_completion)
    append_pack_audit_event(
        workspace.name,
        "readiness_checklist_generated",
        {
            "can_submit_final": bool(gate.get("can_submit_final")),
            "manual_completion_status": manual_completion.get("status"),
            "final_status": "ready_for_manual_submission" if bool(gate.get("can_submit_final")) else "blocked",
        },
    )
    return checklist


def get_submission_binder_evidence_bundle(
    pack_id: str,
    rfq_reference: str | None = None,
) -> Dict[str, Any]:
    workspace = _safe_quote_pack_dir(pack_id)
    if not workspace:
        return _sanitize_audit_payload(
            {
                "status": "not_found",
                "pack_id": _safe_text(pack_id, 220),
                "generated_at": _now_iso(),
                "submission_gate_state": {
                    "status": "not_found",
                    "pack_id": _safe_text(pack_id, 220),
                    "rfq_reference": _safe_text(rfq_reference, 220),
                    "can_prepare_submission": False,
                    "can_submit_final": False,
                    "final_submit_locked": True,
                    "automated_submit_disabled": True,
                },
                "readiness_checklist": {
                    "status": "not_found",
                    "pack_id": _safe_text(pack_id, 220),
                    "manual_completion_required": True,
                    "manual_completion_present": False,
                    "manual_completion_status": "missing",
                    "manual_completion_allowed": False,
                    "manual_completion_blocked_reason": "Manual completion record is required before final submission.",
                    "can_submit_final": False,
                    "final_submit_locked": True,
                    "automated_submit_disabled": True,
                    "blockers": ["No local quote compilation pack matched the requested pack_id."],
                    "warnings": [],
                    "audit_event_count": 0,
                    "audit_warning_count": 0,
                },
                "manual_completion_record": None,
                "audit_trail": [],
                "audit_warning_count": 0,
                "bundle_warnings": ["No local quote compilation pack matched the requested pack_id."],
                "final_submit_locked": True,
                "automated_submit_disabled": True,
                "safety_flags": dict(BINDER_SAFETY_FLAGS),
                "message": "No local quote compilation pack matched the requested pack_id.",
            }
        )

    audit_trail = _read_pack_audit_trail(workspace)
    gate = get_submission_binder_gate(pack_id, rfq_reference)
    manual_completion_validation = _manual_completion_gate(workspace)
    readiness_checklist = get_submission_binder_readiness_checklist(pack_id, rfq_reference)
    bundle = _evidence_bundle_payload(gate, readiness_checklist, manual_completion_validation, audit_trail)
    append_pack_audit_event(
        workspace.name,
        "evidence_bundle_generated",
        {
            "manual_completion_status": manual_completion_validation.get("status"),
            "audit_event_count": int(audit_trail.get("count") or 0),
            "bundle_warning_count": len(bundle.get("bundle_warnings") or []),
            "final_submit_locked": True,
        },
    )
    return bundle


def get_submission_binder_evidence_snapshot(
    pack_id: str,
    rfq_reference: str | None = None,
) -> Dict[str, Any]:
    safe_pack_id = _safe_text(pack_id, 220)
    workspace = _safe_quote_pack_dir(safe_pack_id)
    generated_at = _now_iso()

    if not workspace:
        return _sanitize_audit_payload(
            {
                "status": "not_found",
                "pack_id": safe_pack_id,
                "generated_at": generated_at,
                "evidence_bundle_hash": "",
                "readiness_checklist_hash": "",
                "audit_trail_hash": "",
                "manual_completion_hash": "",
                "verification_status": "unknown",
                "warnings": ["No local quote compilation pack matched the requested pack_id."],
                "message": "No local quote compilation pack matched the requested pack_id.",
            }
        )

    gate = get_submission_binder_gate(safe_pack_id, rfq_reference)
    manual_completion_validation = _manual_completion_gate(workspace)
    audit_trail = _read_pack_audit_trail(workspace)
    readiness_checklist = _readiness_checklist_payload(gate, audit_trail, manual_completion_validation)
    evidence_bundle = _evidence_bundle_payload(gate, readiness_checklist, manual_completion_validation, audit_trail)
    snapshot = _build_evidence_snapshot_payload(
        safe_pack_id,
        rfq_reference,
        gate=gate,
        readiness_checklist=readiness_checklist,
        evidence_bundle=evidence_bundle,
        audit_trail=audit_trail,
        manual_completion_validation=manual_completion_validation,
        persist=True,
    )
    append_pack_audit_event(
        workspace.name,
        "evidence_snapshot_generated",
        {
            "verification_status": snapshot.get("verification_status"),
            "evidence_bundle_hash": snapshot.get("evidence_bundle_hash"),
            "readiness_checklist_hash": snapshot.get("readiness_checklist_hash"),
            "audit_trail_hash": snapshot.get("audit_trail_hash"),
            "manual_completion_hash": snapshot.get("manual_completion_hash"),
            "warning_count": len(snapshot.get("warnings") or []),
        },
    )
    return {
        **snapshot,
        "read_only": True,
        "timestamp": _now_iso(),
    }


def _compliance_archive_verification_status(
    manual_completion_validation: Dict[str, Any],
    submission_proof_validation: Dict[str, Any],
    evidence_snapshot: Dict[str, Any],
    warnings: List[str],
) -> str:
    manual_status = _safe_text(manual_completion_validation.get("status"), 40)
    proof_status = _safe_text(submission_proof_validation.get("status"), 40)
    if manual_status in {"missing", "invalid"} or not manual_completion_validation.get("allowed"):
        return "warning"
    if proof_status == "invalid":
        return "warning"
    if warnings:
        return "warning"
    if _safe_text(evidence_snapshot.get("verification_status"), 40) not in {"verified", "ok", "warning"}:
        return "warning"
    return "verified"


def _compliance_archive_manifest_hash(manifest_payload: Dict[str, Any]) -> str:
    payload = dict(manifest_payload)
    payload.pop("archive_hash", None)
    return _sha256_hex(payload)


def _write_compliance_archive_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        _write_json(path, _sanitize_audit_payload(payload))


def create_compliance_archive(
    pack_id: str,
    rfq_reference: str | None = None,
    operator: Optional[OperatorContext] = None,
) -> Dict[str, Any]:
    safe_pack_id = _safe_text(pack_id, 220)
    workspace = _safe_quote_pack_dir(safe_pack_id)
    created_at = _now_iso()
    if not workspace:
        return _sanitize_audit_payload(
            {
                "status": "not_found",
                "pack_id": safe_pack_id,
                "created_at": created_at,
                "message": "No local quote compilation pack matched the requested pack_id.",
                "warnings": ["No local quote compilation pack matched the requested pack_id."],
            }
        )

    gate = get_submission_binder_gate(safe_pack_id, rfq_reference)
    manual_completion_validation = _manual_completion_gate(workspace)
    submission_proof_validation = _submission_proof_gate(workspace)
    audit_trail = _read_pack_audit_trail(workspace)
    readiness_checklist = _readiness_checklist_payload(gate, audit_trail, manual_completion_validation)
    evidence_bundle = _evidence_bundle_payload(
        gate,
        readiness_checklist,
        manual_completion_validation,
        audit_trail,
    )
    evidence_snapshot = _build_evidence_snapshot_payload(
        safe_pack_id,
        rfq_reference,
        gate=gate,
        readiness_checklist=readiness_checklist,
        evidence_bundle=evidence_bundle,
        audit_trail=audit_trail,
        manual_completion_validation=manual_completion_validation,
        persist=True,
    )

    report_blockers = _compliance_summary_blockers(gate, readiness_checklist, evidence_bundle, manual_completion_validation, workspace)
    report_warnings = _compliance_summary_warnings(readiness_checklist, evidence_bundle, audit_trail, manual_completion_validation)
    if submission_proof_validation.get("status") == "invalid":
        report_warnings.append(_safe_text(submission_proof_validation.get("blocked_reason"), 260) or "Submission proof record is invalid and should be resaved.")
    report_status = _compliance_summary_status(gate, readiness_checklist, evidence_bundle, manual_completion_validation, report_blockers)
    compliance_summary = {
        "status": report_status,
        "pack_id": workspace.name,
        "generated_at": created_at,
        "manual_completion_present": bool(manual_completion_validation.get("status") == "ok"),
        "manual_completion_allowed": bool(manual_completion_validation.get("allowed")),
        "submission_proof_present": bool(submission_proof_validation.get("status") == "ok"),
        "submission_proof_allowed": bool(submission_proof_validation.get("allowed")),
        "submission_proof_status": submission_proof_validation.get("status"),
        "readiness_checklist_available": True,
        "evidence_bundle_available": True,
        "evidence_snapshot_available": True,
        "evidence_snapshot_verification_status": evidence_snapshot.get("verification_status"),
        "evidence_snapshot_hash": evidence_snapshot.get("evidence_bundle_hash"),
        "evidence_snapshot_generated_at": evidence_snapshot.get("generated_at"),
        "audit_event_count": int(audit_trail.get("count") or 0),
        "audit_warning_count": int(audit_trail.get("warning_count") or 0),
        "final_submit_locked": True,
        "automated_submit_disabled": True,
        "can_submit_final": bool(gate.get("can_submit_final") and readiness_checklist.get("can_submit_final") and manual_completion_validation.get("allowed")),
        "blockers": report_blockers,
        "warnings": report_warnings,
        "snapshot_warnings": evidence_snapshot.get("warnings", []),
        "latest_audit_event_summary": _audit_event_summary((audit_trail.get("events") or [])[-1] if isinstance(audit_trail.get("events"), list) and audit_trail.get("events") else None),
        "safety_flags": dict(BINDER_SAFETY_FLAGS),
        "message": "Submission compliance summary is read-only. Manual submission remains locked.",
    }

    report = {
        "status": report_status,
        "pack_id": workspace.name,
        "generated_at": created_at,
        "final_submit_locked": True,
        "automated_submit_disabled": True,
        "manual_completion_present": bool(manual_completion_validation.get("status") == "ok"),
        "manual_completion_allowed": bool(manual_completion_validation.get("allowed")),
        "submission_proof_present": bool(submission_proof_validation.get("status") == "ok"),
        "submission_proof_allowed": bool(submission_proof_validation.get("allowed")),
        "submission_status": report_status,
        "compliance_summary": compliance_summary,
        "readiness_checklist": readiness_checklist,
        "evidence_bundle": evidence_bundle,
        "evidence_snapshot": evidence_snapshot,
        "manual_completion_record": _sanitize_audit_payload(manual_completion_validation.get("manual_completion")) if isinstance(manual_completion_validation.get("manual_completion"), dict) else None,
        "submission_proof_record": _sanitize_audit_payload(submission_proof_validation.get("submission_proof")) if isinstance(submission_proof_validation.get("submission_proof"), dict) else None,
        "audit_summary": {
            "count": int(audit_trail.get("count") or 0),
            "warning_count": int(audit_trail.get("warning_count") or 0),
            "audit_trail_path": audit_trail.get("audit_trail_path"),
            "latest_audit_event_summary": _audit_event_summary((audit_trail.get("events") or [])[-1] if isinstance(audit_trail.get("events"), list) and audit_trail.get("events") else None),
        },
        "latest_audit_events": _sanitize_audit_payload((audit_trail.get("events") or [])[-10:] if isinstance(audit_trail.get("events"), list) else []),
        "blockers": _sanitize_audit_payload(report_blockers),
        "warnings": _sanitize_audit_payload(report_warnings),
        "html": "",
        "message": "Printable compliance report is read-only. Manual submission remains locked.",
    }
    report["html"] = _printable_compliance_report_html(report)

    archives_root = _compliance_archives_root(workspace)
    archives_root.mkdir(parents=True, exist_ok=True)
    archive_id = _next_compliance_archive_id(workspace)
    archive_workspace = _compliance_archive_path(workspace, archive_id)
    suffix = 1
    while archive_workspace.exists():
        archive_id = f"{archive_id}-{suffix}"
        archive_workspace = _compliance_archive_path(workspace, archive_id)
        suffix += 1
    archive_workspace.mkdir(parents=True, exist_ok=False)

    content_paths: Dict[str, Path] = {}
    manifest_warnings = _dedupe_preserve_order([
        *report.get("warnings", []),
        *evidence_snapshot.get("warnings", []),
        *evidence_bundle.get("bundle_warnings", []),
        *readiness_checklist.get("warnings", []),
    ])

    bundle_path = archive_workspace / COMPLIANCE_ARCHIVE_EVIDENCE_BUNDLE_FILENAME
    readiness_path = archive_workspace / COMPLIANCE_ARCHIVE_READINESS_CHECKLIST_FILENAME
    audit_path = archive_workspace / COMPLIANCE_ARCHIVE_AUDIT_TRAIL_FILENAME
    snapshot_path = archive_workspace / COMPLIANCE_ARCHIVE_EVIDENCE_SNAPSHOT_FILENAME
    report_path = archive_workspace / COMPLIANCE_ARCHIVE_PRINTABLE_REPORT_FILENAME
    bundle_content = _sanitize_audit_payload(evidence_bundle)
    readiness_content = _sanitize_audit_payload(readiness_checklist)
    audit_content = _sanitize_audit_payload(audit_trail)
    snapshot_content = _sanitize_audit_payload(evidence_snapshot)
    manual_completion_record = report["manual_completion_record"]
    submission_proof_record = report["submission_proof_record"]

    _write_compliance_archive_file(bundle_path, bundle_content)
    _write_compliance_archive_file(readiness_path, readiness_content)
    _write_compliance_archive_file(audit_path, audit_content)
    _write_compliance_archive_file(snapshot_path, snapshot_content)
    report_path.write_text(report["html"], encoding="utf-8")
    content_paths[COMPLIANCE_ARCHIVE_EVIDENCE_BUNDLE_FILENAME] = bundle_path
    content_paths[COMPLIANCE_ARCHIVE_READINESS_CHECKLIST_FILENAME] = readiness_path
    content_paths[COMPLIANCE_ARCHIVE_AUDIT_TRAIL_FILENAME] = audit_path
    content_paths[COMPLIANCE_ARCHIVE_EVIDENCE_SNAPSHOT_FILENAME] = snapshot_path
    content_paths[COMPLIANCE_ARCHIVE_PRINTABLE_REPORT_FILENAME] = report_path

    if isinstance(manual_completion_record, dict):
        manual_path = archive_workspace / MANUAL_COMPLETION_FILENAME
        _write_compliance_archive_file(manual_path, manual_completion_record)
        content_paths[MANUAL_COMPLETION_FILENAME] = manual_path
    elif isinstance(manual_completion_validation.get("manual_completion"), dict) and manual_completion_validation.get("allowed"):
        manual_path = archive_workspace / MANUAL_COMPLETION_FILENAME
        _write_compliance_archive_file(manual_path, manual_completion_validation.get("manual_completion"))
        content_paths[MANUAL_COMPLETION_FILENAME] = manual_path

    if isinstance(submission_proof_record, dict):
        proof_path = archive_workspace / SUBMISSION_PROOF_FILENAME
        _write_compliance_archive_file(proof_path, submission_proof_record)
        content_paths[SUBMISSION_PROOF_FILENAME] = proof_path

    file_hashes = {
        filename: _compliance_archive_file_hash(path)
        for filename, path in sorted(content_paths.items())
        if path.exists()
    }
    verification_status = _compliance_archive_verification_status(manual_completion_validation, submission_proof_validation, evidence_snapshot, manifest_warnings)
    manifest_payload = {
        "archive_id": archive_id,
        "pack_id": workspace.name,
        "created_at": created_at,
        "file_count": len(file_hashes) + 1,
        "file_hashes": file_hashes,
        "archive_hash": "",
        "verification_status": verification_status,
        "warnings": manifest_warnings,
        "final_submit_locked": True,
        "automated_submit_disabled": True,
        "submission_proof_present": bool(submission_proof_record),
        "submission_proof_hash": file_hashes.get(SUBMISSION_PROOF_FILENAME, ""),
        "archive_path": _relative(archive_workspace),
        "message": "Immutable compliance archive created locally.",
    }
    manifest_payload["archive_hash"] = _compliance_archive_manifest_hash(manifest_payload)
    _write_json(_compliance_archive_manifest_path(archive_workspace), manifest_payload)

    append_pack_audit_event(
        workspace.name,
        "compliance_archive_created",
        _with_operator_audit_payload({
            "archive_id": archive_id,
            "file_count": manifest_payload["file_count"],
            "archive_hash": manifest_payload["archive_hash"],
            "verification_status": verification_status,
            "warning_count": len(manifest_warnings),
        }, operator),
    )

    return {
        "status": "ok",
        "pack_id": workspace.name,
        "created_at": created_at,
        "archive": _sanitize_audit_payload(manifest_payload),
        "archive_path": _relative(archive_workspace),
        "message": "Compliance archive created locally.",
        "read_only": True,
        "timestamp": _now_iso(),
    }


def read_compliance_archives(pack_id: str) -> Dict[str, Any]:
    safe_pack_id = _safe_text(pack_id, 220)
    workspace = _safe_quote_pack_dir(safe_pack_id)
    generated_at = _now_iso()
    if not workspace:
        return _sanitize_audit_payload(
            {
                "status": "not_found",
                "pack_id": safe_pack_id,
                "generated_at": generated_at,
                "archives": [],
                "count": 0,
                "latest_archive_id": "",
                "warnings": ["No local quote compilation pack matched the requested pack_id."],
                "message": "No local quote compilation pack matched the requested pack_id.",
            }
        )

    archives_root = _compliance_archives_root(workspace)
    archives: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if archives_root.exists() and archives_root.is_dir():
        for archive_dir in sorted([path for path in archives_root.iterdir() if path.is_dir()], key=lambda path: _modified_at(path), reverse=True):
            manifest = _read_json(_compliance_archive_manifest_path(archive_dir))
            if isinstance(manifest, dict):
                manifest.setdefault("archive_id", archive_dir.name)
                manifest.setdefault("archive_path", _relative(archive_dir))
                archives.append(_sanitize_audit_payload(manifest))
            else:
                warnings.append(f"Invalid compliance archive manifest skipped: {archive_dir.name}")

    archive_count = len(archives)
    latest_archive_id = archives[0].get("archive_id") if archives else ""
    append_pack_audit_event(
        workspace.name,
        "compliance_archives_listed",
        {
            "archive_count": archive_count,
            "latest_archive_id": latest_archive_id,
            "warning_count": len(warnings),
        },
    )
    return _sanitize_audit_payload(
        {
            "status": "ok",
            "pack_id": workspace.name,
            "generated_at": generated_at,
            "archives": archives,
            "count": archive_count,
            "latest_archive_id": latest_archive_id,
            "warnings": warnings,
            "message": "Compliance archives listed locally.",
            "read_only": True,
            "timestamp": _now_iso(),
        }
    )


def build_compliance_bundle_zip(pack_id: str, archive_id: str | None = None, operator: Optional[OperatorContext] = None) -> Dict[str, Any]:
    safe_pack_id = _safe_text(pack_id, 220)
    workspace = _safe_quote_pack_dir(safe_pack_id)
    generated_at = _now_iso()
    if not workspace:
        return _sanitize_audit_payload(
            {
                "status": "not_found",
                "pack_id": safe_pack_id,
                "generated_at": generated_at,
                "message": "No local quote compilation pack matched the requested pack_id.",
                "warnings": ["No local quote compilation pack matched the requested pack_id."],
            }
        )

    archive_manifest: Optional[Dict[str, Any]] = None
    archive_workspace: Optional[Path] = None
    if archive_id:
        candidate = _compliance_archive_path(workspace, _safe_text(archive_id, 160))
        manifest = _read_json(_compliance_archive_manifest_path(candidate))
        if isinstance(manifest, dict):
            archive_workspace = candidate
            archive_manifest = manifest
    else:
        archive_manifest = _compliance_archive_latest_manifest(workspace)
        if archive_manifest:
            archive_workspace = _compliance_archive_path(workspace, _safe_text(archive_manifest.get("archive_id"), 160))

    if not archive_workspace or not archive_workspace.exists():
        if archive_id:
            return _sanitize_audit_payload(
                {
                    "status": "not_found",
                    "pack_id": workspace.name,
                    "generated_at": generated_at,
                    "archive_id": _safe_text(archive_id, 160),
                    "message": "Compliance archive not found.",
                    "warnings": ["Compliance archive not found."],
                }
            )
        created = create_compliance_archive(pack_id, operator=operator)
        if created.get("status") != "ok":
            return _sanitize_audit_payload(created)
        archive_manifest = created.get("archive") if isinstance(created.get("archive"), dict) else None
        archive_workspace = _compliance_archive_path(workspace, _safe_text(created.get("archive", {}).get("archive_id") if isinstance(created.get("archive"), dict) else "", 160))

    if not archive_manifest and archive_workspace:
        archive_manifest = _read_json(_compliance_archive_manifest_path(archive_workspace))
    if not archive_manifest or not archive_workspace:
        return _sanitize_audit_payload(
            {
                "status": "not_found",
                "pack_id": workspace.name,
                "generated_at": generated_at,
                "message": "Compliance archive not found.",
                "warnings": ["Compliance archive not found."],
            }
        )

    archive_id_safe = _safe_text(archive_manifest.get("archive_id") or archive_workspace.name, 160)
    export_path = _compliance_archive_export_path(archive_workspace, archive_id_safe)
    with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as archive_zip:
        for current, dirs, files in os.walk(archive_workspace):
            current_path = Path(current)
            dirs[:] = [name for name in dirs if name != COMPLIANCE_ARCHIVE_EXPORTS_DIRNAME]
            for filename in sorted(files):
                if filename.endswith(".zip"):
                    continue
                path = current_path / filename
                if not path.is_file():
                    continue
                archive_zip.write(path, arcname=str(path.relative_to(archive_workspace)))

    append_pack_audit_event(
        workspace.name,
        "compliance_archive_zip_exported",
        _with_operator_audit_payload({
            "archive_id": archive_id_safe,
            "zip_path": _relative(export_path),
            "file_count": int(archive_manifest.get("file_count") or 0),
        }, operator),
    )
    return {
        "status": "ok",
        "pack_id": workspace.name,
        "generated_at": generated_at,
        "archive_id": archive_id_safe,
        "archive_path": _relative(archive_workspace),
        "zip_path": _relative(export_path),
        "zip_file_path": str(export_path),
        "file_count": int(archive_manifest.get("file_count") or 0),
        "archive": _sanitize_audit_payload(archive_manifest),
        "message": "Compliance archive bundle created locally.",
        "read_only": True,
        "timestamp": _now_iso(),
    }


def _compliance_summary_blockers(
    gate: Dict[str, Any],
    readiness_checklist: Dict[str, Any],
    evidence_bundle: Dict[str, Any],
    manual_completion: Dict[str, Any],
    workspace: Optional[Path],
) -> List[str]:
    blockers: List[str] = []
    if not workspace or gate.get("status") != "ok":
        blockers.append("No local quote compilation pack matched the requested pack_id.")

    gate_blockers = [
        _safe_text(item, 260)
        for item in gate.get("blockers") or []
        if _safe_text(item, 260)
    ]
    blockers.extend(gate_blockers)

    manual_reason = _safe_text(manual_completion.get("blocked_reason"), 500)
    if not manual_completion.get("allowed", False):
        blockers.append(manual_reason or "Manual completion record is required before final submission.")

    if readiness_checklist.get("status") == "not_found" or not readiness_checklist.get("readiness_status"):
        blockers.append("Readiness checklist is unavailable for this pack.")

    if evidence_bundle.get("status") == "not_found" or not evidence_bundle.get("submission_gate_state"):
        blockers.append("Evidence bundle is unavailable for this pack.")

    return _dedupe_preserve_order(blockers)


def _compliance_summary_warnings(
    readiness_checklist: Dict[str, Any],
    evidence_bundle: Dict[str, Any],
    audit_trail: Dict[str, Any],
    manual_completion: Dict[str, Any],
) -> List[str]:
    warnings: List[str] = []
    workspace = _safe_quote_pack_dir(readiness_checklist.get("pack_id") or evidence_bundle.get("pack_id") or "")
    submission_proof = _submission_proof_gate(workspace) if workspace else {
        "status": "missing",
        "allowed": False,
        "blocked_reason": "Submission proof record has not been saved yet.",
    }
    audit_warning_count = int(audit_trail.get("warning_count") or 0)
    if audit_warning_count:
        warnings.append(f"Audit trail contains {audit_warning_count} invalid line(s) that were skipped.")

    readiness_warnings = readiness_checklist.get("warnings")
    if isinstance(readiness_warnings, list):
        warnings.extend(_safe_text(item, 260) for item in readiness_warnings if _safe_text(item, 260))

    bundle_warnings = evidence_bundle.get("bundle_warnings")
    if isinstance(bundle_warnings, list):
        warnings.extend(_safe_text(item, 260) for item in bundle_warnings if _safe_text(item, 260))

    if manual_completion.get("status") == "invalid":
        warnings.append(_safe_text(manual_completion.get("blocked_reason"), 260) or "Manual completion record is invalid and should be resaved.")
    if submission_proof.get("status") == "invalid":
        warnings.append(_safe_text(submission_proof.get("blocked_reason"), 260) or "Submission proof record is invalid and should be resaved.")

    return _dedupe_preserve_order(warnings)


def _compliance_summary_status(
    gate: Dict[str, Any],
    readiness_checklist: Dict[str, Any],
    evidence_bundle: Dict[str, Any],
    manual_completion: Dict[str, Any],
    blockers: List[str],
) -> str:
    if gate.get("status") != "ok" or not gate.get("matched_binder"):
        return "unknown"
    if not manual_completion.get("status") or manual_completion.get("status") != "ok":
        return "blocked"
    if not bool(manual_completion.get("allowed")):
        return "blocked"
    if blockers:
        return "locked"
    if bool(readiness_checklist.get("checklist_text")) and bool(evidence_bundle.get("pack_id")) and bool(gate.get("can_submit_final")):
        return "ready_manual_only"
    return "locked"


def get_submission_binder_compliance_summary(
    pack_id: str,
    rfq_reference: str | None = None,
) -> Dict[str, Any]:
    safe_pack_id = _safe_text(pack_id, 220)
    workspace = _safe_quote_pack_dir(safe_pack_id)
    generated_at = _now_iso()

    if not workspace:
        return _sanitize_audit_payload(
            {
                "status": "unknown",
                "pack_id": safe_pack_id,
                "generated_at": generated_at,
                "manual_completion_present": False,
                "manual_completion_allowed": False,
                "submission_proof_present": False,
                "submission_proof_allowed": False,
                "submission_proof_status": "missing",
                "submission_proof_saved_at": "",
                "readiness_checklist_available": False,
                "evidence_bundle_available": False,
                "audit_event_count": 0,
                "audit_warning_count": 0,
                "final_submit_locked": True,
                "automated_submit_disabled": True,
                "can_submit_final": False,
                "status_detail": "No local quote compilation pack matched the requested pack_id.",
                "blockers": ["No local quote compilation pack matched the requested pack_id."],
                "warnings": [],
                "latest_audit_event_summary": "",
                "safety_flags": dict(BINDER_SAFETY_FLAGS),
                "message": "No local quote compilation pack matched the requested pack_id.",
            }
        )

    gate = get_submission_binder_gate(safe_pack_id, rfq_reference)
    manual_completion = _manual_completion_gate(workspace)
    submission_proof = _submission_proof_gate(workspace)
    audit_trail = _read_pack_audit_trail(workspace)
    readiness_checklist = _readiness_checklist_payload(gate, audit_trail, manual_completion)
    evidence_bundle = _evidence_bundle_payload(gate, readiness_checklist, manual_completion, audit_trail)

    readiness_available = readiness_checklist.get("status") != "not_found"
    evidence_available = evidence_bundle.get("status") != "not_found"
    manual_completion_present = bool(manual_completion.get("status") == "ok")
    manual_completion_allowed = bool(manual_completion.get("allowed"))
    submission_proof_present = bool(submission_proof.get("status") == "ok")
    submission_proof_allowed = bool(submission_proof.get("allowed"))
    can_submit_final = bool(gate.get("can_submit_final") and readiness_available and evidence_available)
    evidence_snapshot = _build_evidence_snapshot_payload(
        safe_pack_id,
        rfq_reference,
        gate=gate,
        readiness_checklist=readiness_checklist,
        evidence_bundle=evidence_bundle,
        audit_trail=audit_trail,
        manual_completion_validation=manual_completion,
        persist=True,
    )
    blockers = _compliance_summary_blockers(gate, readiness_checklist, evidence_bundle, manual_completion, workspace)
    warnings = _compliance_summary_warnings(readiness_checklist, evidence_bundle, audit_trail, manual_completion)
    latest_event = audit_trail.get("events")[-1] if isinstance(audit_trail.get("events"), list) and audit_trail.get("events") else None
    status = _compliance_summary_status(gate, readiness_checklist, evidence_bundle, manual_completion, blockers)

    summary = {
        "status": status,
        "pack_id": workspace.name,
        "generated_at": generated_at,
        "manual_completion_present": manual_completion_present,
        "manual_completion_allowed": manual_completion_allowed,
        "submission_proof_present": submission_proof_present,
        "submission_proof_allowed": submission_proof_allowed,
        "submission_proof_status": submission_proof.get("status"),
        "submission_proof_blocked_reason": submission_proof.get("blocked_reason"),
        "submission_proof_saved_at": _safe_text(submission_proof.get("submission_proof", {}).get("saved_at") if isinstance(submission_proof.get("submission_proof"), dict) else "", 80),
        "readiness_checklist_available": readiness_available,
        "evidence_bundle_available": evidence_available,
        "evidence_snapshot_available": True,
        "evidence_snapshot_verification_status": evidence_snapshot.get("verification_status"),
        "evidence_snapshot_hash": evidence_snapshot.get("evidence_bundle_hash"),
        "evidence_snapshot_generated_at": evidence_snapshot.get("generated_at"),
        "audit_event_count": int(audit_trail.get("count") or 0),
        "audit_warning_count": int(audit_trail.get("warning_count") or 0),
        "final_submit_locked": True,
        "automated_submit_disabled": True,
        "can_submit_final": can_submit_final,
        "blockers": blockers,
        "warnings": warnings,
        "snapshot_warnings": evidence_snapshot.get("warnings", []),
        "latest_audit_event_summary": _audit_event_summary(latest_event),
        "safety_flags": dict(BINDER_SAFETY_FLAGS),
        "message": "Submission compliance summary is read-only. Manual submission remains locked.",
    }
    append_pack_audit_event(
        workspace.name,
        "compliance_summary_generated",
        {
            "status": status,
            "manual_completion_present": manual_completion_present,
            "manual_completion_allowed": manual_completion_allowed,
            "submission_proof_present": submission_proof_present,
            "submission_proof_allowed": submission_proof_allowed,
            "submission_proof_saved_at": summary["submission_proof_saved_at"],
            "readiness_checklist_available": readiness_available,
            "evidence_bundle_available": evidence_available,
            "audit_event_count": summary["audit_event_count"],
            "audit_warning_count": summary["audit_warning_count"],
            "can_submit_final": can_submit_final,
        },
    )
    return _sanitize_audit_payload(summary)


def append_pack_audit_event(pack_id: str, event_type: str, payload: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    workspace = _pack_audit_workspace(pack_id, create=True)
    if not workspace:
        return None

    event = {
        "event_id": uuid.uuid4().hex,
        "timestamp": _now_iso(),
        "pack_id": workspace.name,
        "event_type": _safe_text(event_type, 160) or "event",
        "payload": _sanitize_audit_payload(payload or {}),
    }

    path = _audit_trail_path(workspace)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    except OSError:
        return event
    return event


def _manual_completion_has_forbidden_fields(payload: Dict[str, Any]) -> bool:
    return bool(_manual_completion_forbidden_field_hits(payload))


def _manual_completion_forbidden_field_hits(payload: Dict[str, Any], fields: Optional[Iterable[str]] = None) -> List[str]:
    if not isinstance(payload, dict):
        return []
    target_fields = list(fields or payload.keys())
    hits: List[str] = []
    for field in target_fields:
        if field not in payload:
            continue
        value = payload.get(field)
        if value in (None, ""):
            continue
        haystack = f"{field} {_safe_text(value, 2000)}".lower()
        if any(re.search(rf"\b{re.escape(keyword)}\b", haystack) for keyword in FORBIDDEN_MANUAL_COMPLETION_KEYWORDS):
            hits.append(str(field))
    return hits


def _normalize_manual_completion_file_names(value: Any) -> List[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError("uploaded_file_names must be a list of strings.")

    file_names: List[str] = []
    for item in values[: MANUAL_COMPLETION_LIMITS["uploaded_file_names_count"]]:
        if item is None:
            continue
        text = str(item).replace("\n", " ").replace("\r", " ").strip()
        if not text:
            continue
        if len(text) > MANUAL_COMPLETION_LIMITS["uploaded_file_name"]:
            raise ValueError("Each uploaded file name must be 220 characters or fewer.")
        file_names.append(text)
    return file_names


def _normalize_manual_completion_payload(workspace: Path, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Manual completion payload must be a JSON object.")

    allowed_fields = {
        "submitted_by",
        "submitted_at",
        "portal_name",
        "portal_reference",
        "notes",
        "uploaded_file_names",
    }
    extra_fields = [key for key in payload.keys() if key not in allowed_fields]
    if extra_fields:
        raise ValueError(f"Unsupported field(s): {', '.join(sorted(str(field) for field in extra_fields))}.")

    if _manual_completion_has_forbidden_fields(payload):
        raise ValueError("Manual completion records must not include passwords, OTPs, CAPTCHA values, or portal credentials.")

    submitted_by = _strict_text(payload.get("submitted_by"), MANUAL_COMPLETION_LIMITS["submitted_by"], "submitted_by")
    submitted_at = _strict_text(payload.get("submitted_at"), MANUAL_COMPLETION_LIMITS["submitted_at"], "submitted_at")
    portal_name = _strict_text(payload.get("portal_name"), MANUAL_COMPLETION_LIMITS["portal_name"], "portal_name")
    portal_reference = _strict_text(payload.get("portal_reference"), MANUAL_COMPLETION_LIMITS["portal_reference"], "portal_reference")
    notes_raw = payload.get("notes")
    notes = "" if notes_raw in (None, "") else str(notes_raw).replace("\n", " ").replace("\r", " ").strip()
    if len(notes) > MANUAL_COMPLETION_LIMITS["notes"]:
        raise ValueError("notes exceeds the maximum length of 2000 characters.")
    uploaded_file_names = _normalize_manual_completion_file_names(payload.get("uploaded_file_names"))

    return {
        "pack_id": workspace.name,
        "submitted_by": submitted_by,
        "submitted_at": submitted_at,
        "portal_name": portal_name,
        "portal_reference": portal_reference,
        "notes": notes,
        "uploaded_file_names": uploaded_file_names,
        "saved_at": _now_iso(),
        "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
    }


def _manual_completion_validation_result(workspace: Path, payload: Optional[Any]) -> Dict[str, Any]:
    path = _manual_completion_path(workspace)
    missing_reason = "Manual completion record is required before final submission."
    base_result = {
        "required": True,
        "allowed": False,
        "blocked_reason": missing_reason,
        "reason_code": "manual_completion_missing",
        "status": "missing",
        "pack_id": workspace.name,
        "manual_completion": None,
        "manual_completion_path": _relative(path),
        "required_fields": list(MANUAL_COMPLETION_REQUIRED_FIELDS),
        "missing_fields": list(MANUAL_COMPLETION_REQUIRED_FIELDS),
        "forbidden_fields": [],
        "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
    }

    if not path.exists() or not path.is_file():
        return base_result

    if not isinstance(payload, dict):
        return {
            **base_result,
            "reason_code": "manual_completion_invalid_json",
            "status": "invalid",
            "blocked_reason": "Manual completion record is invalid JSON or unreadable.",
        }

    missing_fields = [field for field in MANUAL_COMPLETION_REQUIRED_FIELDS if field not in payload]
    if missing_fields:
        return {
            **base_result,
            "reason_code": "manual_completion_missing_fields",
            "status": "invalid",
            "blocked_reason": f"Manual completion record is incomplete: missing {', '.join(missing_fields)}.",
            "missing_fields": missing_fields,
        }

    try:
        submitted_by = _strict_text(payload.get("submitted_by"), MANUAL_COMPLETION_LIMITS["submitted_by"], "submitted_by")
        submitted_at = _strict_text(payload.get("submitted_at"), MANUAL_COMPLETION_LIMITS["submitted_at"], "submitted_at")
        portal_name = _strict_text(payload.get("portal_name"), MANUAL_COMPLETION_LIMITS["portal_name"], "portal_name")
        portal_reference = _strict_text(payload.get("portal_reference"), MANUAL_COMPLETION_LIMITS["portal_reference"], "portal_reference")
        notes_raw = payload.get("notes")
        notes = "" if notes_raw in (None, "") else _strict_text(notes_raw, MANUAL_COMPLETION_LIMITS["notes"], "notes")
        uploaded_raw = payload.get("uploaded_file_names")
        if uploaded_raw is None:
            raise ValueError("uploaded_file_names is required.")
        if not isinstance(uploaded_raw, list):
            raise ValueError("uploaded_file_names must be a list of strings.")
        uploaded_file_names = _normalize_manual_completion_file_names(uploaded_raw)
    except ValueError as exc:
        return {
            **base_result,
            "reason_code": "manual_completion_invalid_fields",
            "status": "invalid",
            "blocked_reason": str(exc),
        }

    forbidden_fields = _manual_completion_forbidden_field_hits(payload, MANUAL_COMPLETION_REVIEW_FIELDS)
    if forbidden_fields:
        return {
            **base_result,
            "reason_code": "manual_completion_credential_like_content",
            "status": "invalid",
            "blocked_reason": "Manual completion record contains credential-like content and cannot be used for final submission.",
            "forbidden_fields": forbidden_fields,
        }

    manual_completion = {
        "pack_id": workspace.name,
        "submitted_by": submitted_by,
        "submitted_at": submitted_at,
        "portal_name": portal_name,
        "portal_reference": portal_reference,
        "notes": notes,
        "uploaded_file_names": uploaded_file_names,
        "saved_at": _safe_text(payload.get("saved_at"), 80) or _now_iso(),
        "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
    }
    if payload.get("saved_by") not in (None, ""):
        manual_completion["saved_by"] = _safe_text(payload.get("saved_by"), MANUAL_COMPLETION_LIMITS["submitted_by"])
    if payload.get("completed_by") not in (None, ""):
        manual_completion["completed_by"] = _safe_text(payload.get("completed_by"), MANUAL_COMPLETION_LIMITS["submitted_by"])

    return {
        **base_result,
        "allowed": True,
        "blocked_reason": "",
        "reason_code": "manual_completion_valid",
        "status": "ok",
        "missing_fields": [],
        "forbidden_fields": [],
        "manual_completion": manual_completion,
    }


def _manual_completion_gate(workspace: Path) -> Dict[str, Any]:
    path = _manual_completion_path(workspace)
    raw = _read_json(path)
    return _manual_completion_validation_result(workspace, raw)


def _submission_proof_has_forbidden_fields(payload: Dict[str, Any]) -> bool:
    return bool(_submission_proof_forbidden_field_hits(payload))


def _submission_proof_forbidden_field_hits(payload: Dict[str, Any], fields: Optional[Iterable[str]] = None) -> List[str]:
    if not isinstance(payload, dict):
        return []
    target_fields = list(fields or payload.keys())
    hits: List[str] = []
    for field in target_fields:
        if field not in payload:
            continue
        value = payload.get(field)
        if value in (None, ""):
            continue
        haystack = f"{field} {_safe_text(value, 2000)}".lower()
        if any(re.search(rf"\b{re.escape(keyword)}\b", haystack) for keyword in FORBIDDEN_MANUAL_COMPLETION_KEYWORDS):
            hits.append(str(field))
    return hits


def _normalize_submission_proof_files(value: Any) -> List[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError("uploaded_files must be a list of strings.")

    file_names: List[str] = []
    for item in values[: SUBMISSION_PROOF_LIMITS["uploaded_files_count"]]:
        if item is None:
            continue
        text = str(item).replace("\n", " ").replace("\r", " ").strip()
        if not text:
            continue
        if len(text) > SUBMISSION_PROOF_LIMITS["uploaded_file_name"]:
            raise ValueError("Each uploaded file name must be 220 characters or fewer.")
        file_names.append(text)
    return file_names


def validate_submission_proof(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Submission proof payload must be a JSON object.")
    if len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")) > 64 * 1024:
        raise ValueError("Submission proof payload exceeds the maximum allowed size.")

    allowed_fields = set(SUBMISSION_PROOF_REQUIRED_FIELDS) | set(SUBMISSION_PROOF_OPTIONAL_FIELDS)
    extra_fields = [key for key in payload.keys() if key not in allowed_fields]
    if extra_fields:
        raise ValueError(f"Unsupported field(s): {', '.join(sorted(str(field) for field in extra_fields))}.")

    if _submission_proof_has_forbidden_fields(payload):
        raise ValueError("Submission proof records must not include passwords, OTPs, CAPTCHA values, tokens, cookies, API keys, session IDs, or portal credentials.")

    submitted_by = _strict_text(payload.get("submitted_by"), SUBMISSION_PROOF_LIMITS["submitted_by"], "submitted_by")
    submission_timestamp = _strict_text(payload.get("submission_timestamp"), SUBMISSION_PROOF_LIMITS["submission_timestamp"], "submission_timestamp")
    portal_name = _strict_text(payload.get("portal_name"), SUBMISSION_PROOF_LIMITS["portal_name"], "portal_name")
    portal_reference = _strict_text(payload.get("portal_reference"), SUBMISSION_PROOF_LIMITS["portal_reference"], "portal_reference")
    proof_notes = _strict_text(payload.get("proof_notes"), SUBMISSION_PROOF_LIMITS["proof_notes"], "proof_notes")

    buyer_reference = payload.get("buyer_reference")
    if buyer_reference in (None, ""):
        buyer_reference_text = ""
    else:
        buyer_reference_text = _strict_text(buyer_reference, SUBMISSION_PROOF_LIMITS["buyer_reference"], "buyer_reference")

    confirmation_message = payload.get("confirmation_message")
    if confirmation_message in (None, ""):
        confirmation_message_text = ""
    else:
        confirmation_message_text = _strict_text(confirmation_message, SUBMISSION_PROOF_LIMITS["confirmation_message"], "confirmation_message")

    screenshot_notes = payload.get("screenshot_notes")
    if screenshot_notes in (None, ""):
        screenshot_notes_text = ""
    else:
        screenshot_notes_text = _strict_text(screenshot_notes, SUBMISSION_PROOF_LIMITS["screenshot_notes"], "screenshot_notes")

    uploaded_files = _normalize_submission_proof_files(payload.get("uploaded_files"))

    proof = {
        "submitted_by": submitted_by,
        "submission_timestamp": submission_timestamp,
        "portal_name": portal_name,
        "portal_reference": portal_reference,
        "proof_notes": proof_notes,
        "uploaded_files": uploaded_files,
        "saved_at": _now_iso(),
        "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
        "proof_safety": {
            "local_only": True,
            "no_credentials": True,
            "no_portal_calls": True,
            "no_final_submit": True,
            "no_upload": True,
            "no_email": True,
        },
    }
    if buyer_reference_text:
        proof["buyer_reference"] = buyer_reference_text
    if confirmation_message_text:
        proof["confirmation_message"] = confirmation_message_text
    if screenshot_notes_text:
        proof["screenshot_notes"] = screenshot_notes_text
    return proof


def _submission_proof_validation_result(workspace: Path, payload: Optional[Any]) -> Dict[str, Any]:
    path = _submission_proof_path(workspace)
    missing_reason = "Submission proof record is optional but not yet saved for this pack."
    base_result = {
        "required": False,
        "allowed": False,
        "blocked_reason": missing_reason,
        "reason_code": "submission_proof_missing",
        "status": "missing",
        "pack_id": workspace.name,
        "submission_proof": None,
        "submission_proof_path": _relative(path),
        "required_fields": list(SUBMISSION_PROOF_REQUIRED_FIELDS),
        "missing_fields": list(SUBMISSION_PROOF_REQUIRED_FIELDS),
        "forbidden_fields": [],
        "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
    }

    if not path.exists() or not path.is_file():
        return base_result

    if not isinstance(payload, dict):
        return {
            **base_result,
            "reason_code": "submission_proof_invalid_json",
            "status": "invalid",
            "blocked_reason": "Submission proof record is invalid JSON or unreadable.",
        }

    missing_fields = [field for field in SUBMISSION_PROOF_REQUIRED_FIELDS if field not in payload]
    if missing_fields:
        return {
            **base_result,
            "reason_code": "submission_proof_missing_fields",
            "status": "invalid",
            "blocked_reason": f"Submission proof record is incomplete: missing {', '.join(missing_fields)}.",
            "missing_fields": missing_fields,
        }

    extra_fields = [key for key in payload.keys() if key not in set(SUBMISSION_PROOF_REQUIRED_FIELDS) | set(SUBMISSION_PROOF_OPTIONAL_FIELDS) | set(SUBMISSION_PROOF_INTERNAL_FIELDS)]
    if extra_fields:
        return {
            **base_result,
            "reason_code": "submission_proof_invalid_fields",
            "status": "invalid",
            "blocked_reason": f"Submission proof record contains unsupported field(s): {', '.join(sorted(str(field) for field in extra_fields))}.",
        }

    try:
        proof = validate_submission_proof({key: payload.get(key) for key in list(SUBMISSION_PROOF_REQUIRED_FIELDS) + list(SUBMISSION_PROOF_OPTIONAL_FIELDS)})
    except ValueError as exc:
        reason_text = str(exc)
        return {
            **base_result,
            "reason_code": "submission_proof_invalid_fields",
            "status": "invalid",
            "blocked_reason": reason_text,
            "forbidden_fields": _submission_proof_forbidden_field_hits(payload, SUBMISSION_PROOF_REVIEW_FIELDS),
        }

    proof["pack_id"] = workspace.name
    proof["saved_at"] = _safe_text(payload.get("saved_at"), 80) or proof.get("saved_at")
    proof["safety"] = dict(MANUAL_COMPLETION_SAFETY_FLAGS)
    proof["proof_safety"] = {
        "local_only": True,
        "no_credentials": True,
        "no_portal_calls": True,
        "no_final_submit": True,
        "no_upload": True,
        "no_email": True,
    }

    return {
        **base_result,
        "allowed": True,
        "blocked_reason": "",
        "reason_code": "submission_proof_valid",
        "status": "ok",
        "missing_fields": [],
        "forbidden_fields": [],
        "submission_proof": proof,
    }


def _submission_proof_gate(workspace: Path) -> Dict[str, Any]:
    path = _submission_proof_path(workspace)
    raw = _read_json(path)
    return _submission_proof_validation_result(workspace, raw)


def _submission_proof_detail(workspace: Path) -> Dict[str, Any]:
    data = _safe_read_pack_json(workspace, SUBMISSION_PROOF_FILENAME)
    if not isinstance(data, dict):
        return {
            "status": "not_found",
            "message": "No submission proof record has been saved for this pack.",
            "pack_id": workspace.name,
            "submission_proof": None,
            "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
        }
    validation = _submission_proof_validation_result(workspace, data)
    proof_record = validation.get("submission_proof") if validation.get("allowed") else None
    return {
        "status": validation.get("status", "ok"),
        "pack_id": workspace.name,
        "submission_proof": proof_record,
        "saved_at": _safe_text(data.get("saved_at"), 80),
        "validation": validation,
        "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
    }


def _safe_name(value: Any, fallback: str = "RFQ") -> str:
    text = _safe_text(value or fallback, 160)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _slug(value: Any) -> str:
    text = _safe_text(value, 500).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _safe_number(value: Any) -> Optional[float]:
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace("R", "").replace(",", "").replace("%", "").strip()
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def _contains_sensitive_marker(path: Path) -> bool:
    lowered = str(path).lower()
    return any(marker in lowered for marker in SENSITIVE_PATH_MARKERS)


def _first(record: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _read_json(path: Path) -> Optional[Any]:
    if _contains_sensitive_marker(path) or not path.exists() or not path.is_file():
        return None
    try:
        if path.stat().st_size > MAX_JSON_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _modified_at(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return ""


def _file_metadata(path: Path, source: str) -> Dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {
        "path": _relative(path),
        "name": path.name,
        "extension": path.suffix.lower(),
        "source": source,
        "size_bytes": size,
        "modified_at": _modified_at(path),
    }


def _iter_safe_files(directory: Path) -> Tuple[List[Path], bool]:
    if not directory.exists() or not directory.is_dir():
        return [], False

    root_depth = len(directory.parts)
    files: List[Path] = []
    limit_reached = False

    for current, dirs, names in os.walk(directory):
        current_path = Path(current)
        depth = len(current_path.parts) - root_depth
        if depth >= MAX_SCAN_DEPTH:
            dirs[:] = []
        dirs[:] = [
            name
            for name in dirs
            if not name.startswith(".") and not _contains_sensitive_marker(current_path / name)
        ]
        for name in sorted(names):
            path = current_path / name
            if _contains_sensitive_marker(path):
                continue
            files.append(path)
            if len(files) >= MAX_SCAN_FILES_PER_DIR:
                limit_reached = True
                return files, limit_reached

    return files, limit_reached


def _directory_status(name: str, directory: Path, files: List[Path], limit_reached: bool) -> Dict[str, Any]:
    return {
        "source": name,
        "path": _relative(directory),
        "exists": directory.exists(),
        "is_dir": directory.is_dir(),
        "scanned_files": len(files),
        "doc_artifact_count": sum(1 for item in files if item.suffix.lower() in SAFE_DOC_EXTENSIONS),
        "json_file_count": sum(1 for item in files if item.suffix.lower() == ".json"),
        "scan_limit_reached": limit_reached,
    }


def _load_rfq_records() -> List[Dict[str, Any]]:
    data = _read_json(RFQ_STATE_FILE)
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    records: List[Dict[str, Any]] = []
    if isinstance(items, dict):
        for record_id, record in items.items():
            if isinstance(record, dict):
                records.append({**record, "_record_id": str(record_id)})
    elif isinstance(items, list):
        for index, record in enumerate(items):
            if isinstance(record, dict):
                fallback_id = _safe_text(_first(record, ("id", "rfq_id", "reference")) or f"rfq-{index}")
                records.append({**record, "_record_id": fallback_id})
    return records


def _artifact_inventory() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    artifacts: List[Dict[str, Any]] = []
    sources_checked: List[Dict[str, Any]] = []
    for source_name, directory in SOURCE_DIRS.items():
        files, limit_reached = _iter_safe_files(directory)
        sources_checked.append(_directory_status(source_name, directory, files, limit_reached))
        for path in files:
            if path.suffix.lower() in SAFE_DOC_EXTENSIONS:
                artifacts.append(_file_metadata(path, source_name))
    return artifacts, sources_checked


def _record_reference(record: Dict[str, Any]) -> str:
    return _safe_text(_first(record, ("rfq_id", "reference", "buyer_rfq_number", "rfq_reference", "_record_id")) or "RFQ")


def _record_title(record: Dict[str, Any]) -> str:
    return _safe_text(_first(record, ("title", "description", "name", "subject")) or _record_reference(record), 700)


def _record_latest_activity(record: Dict[str, Any]) -> str:
    candidates = [
        _first(record, ("updated_at", "finished_at", "checked_at", "proof_timestamp", "created_at", "started_at"))
    ]
    audit_log = record.get("audit_log") or record.get("lifecycle_trace") or []
    if isinstance(audit_log, list):
        for event in audit_log[-5:]:
            if isinstance(event, dict):
                candidates.append(_first(event, ("at", "timestamp", "created_at")))
    values = [_safe_text(value, 80) for value in candidates if value]
    return max(values) if values else ""


def _artifact_text(artifact: Dict[str, Any]) -> str:
    return _slug(f"{artifact.get('path', '')} {artifact.get('name', '')}")


def _matches_record(artifact: Dict[str, Any], record: Dict[str, Any]) -> bool:
    haystack = _artifact_text(artifact)
    keys = [
        _slug(_record_reference(record)),
        _slug(record.get("_record_id")),
        _slug(_record_title(record)),
        _slug(record.get("quote_number")),
    ]
    keys = [key for key in keys if len(key) >= 5]
    return any(key in haystack or haystack in key for key in keys)


def _artifacts_for_record(record: Dict[str, Any], artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matched = [artifact for artifact in artifacts if _matches_record(artifact, record)]
    source_paths = record.get("document_paths") or []
    if isinstance(source_paths, dict):
        source_paths = list(source_paths.values())
    if isinstance(source_paths, list):
        for item in source_paths[:40]:
            text = _safe_text(item, 500)
            if text and not _contains_sensitive_marker(Path(text)):
                matched.append(
                    {
                        "path": text,
                        "name": Path(text).name or text,
                        "extension": Path(text).suffix.lower(),
                        "source": "rfq_lifecycle.document_paths",
                        "size_bytes": 0,
                        "modified_at": "",
                    }
                )
    quote_artifacts = record.get("quote_pack_artifacts") or []
    if isinstance(quote_artifacts, dict):
        quote_artifacts = list(quote_artifacts.values())
    if isinstance(quote_artifacts, list):
        for item in quote_artifacts[:40]:
            text = _safe_text(item, 500)
            if text and not _contains_sensitive_marker(Path(text)):
                matched.append(
                    {
                        "path": text,
                        "name": Path(text).name or text,
                        "extension": Path(text).suffix.lower(),
                        "source": "rfq_lifecycle.quote_pack_artifacts",
                        "size_bytes": 0,
                        "modified_at": "",
                    }
                )
    return _dedupe_artifacts(matched)


def _dedupe_artifacts(artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for artifact in artifacts:
        key = artifact.get("path") or artifact.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(artifact)
    return out


def _has_artifact(artifacts: List[Dict[str, Any]], terms: Iterable[str]) -> bool:
    term_list = list(terms)
    for artifact in artifacts:
        text = f"{artifact.get('path', '')} {artifact.get('name', '')}".lower()
        if any(term in text for term in term_list):
            return True
    return False


def _filter_artifacts(artifacts: List[Dict[str, Any]], terms: Iterable[str]) -> List[Dict[str, Any]]:
    term_list = list(terms)
    return [
        artifact
        for artifact in artifacts
        if any(term in f"{artifact.get('path', '')} {artifact.get('name', '')}".lower() for term in term_list)
    ]


def _pricing_found(record: Dict[str, Any], artifacts: List[Dict[str, Any]]) -> bool:
    pricing_result = record.get("pricing_result")
    if isinstance(pricing_result, dict) and pricing_result.get("priced") is True:
        return True
    return _has_artifact(artifacts, ("pricing", "price", "schedule", "rates", "buyer_pricing"))


def _estimated_profit(record: Dict[str, Any]) -> Optional[float]:
    direct = _safe_number(_first(record, ("estimated_profit", "profit", "expected_profit")))
    if direct is not None:
        return direct
    pricing_result = record.get("pricing_result")
    if isinstance(pricing_result, dict):
        return _safe_number(_first(pricing_result, ("estimated_profit", "existing_profit")))
    return None


def _margin_percent(record: Dict[str, Any]) -> Optional[float]:
    direct = _safe_number(_first(record, ("margin_percent", "estimated_margin", "estimated_margin_percent")))
    if direct is None and isinstance(record.get("pricing_result"), dict):
        direct = _safe_number(_first(record["pricing_result"], ("estimated_margin_percent", "existing_margin_percent")))
    if direct is not None and 0 < direct <= 1:
        return round(direct * 100, 2)
    return direct


def _estimated_value(record: Dict[str, Any], profit: Optional[float], margin: Optional[float]) -> Optional[float]:
    direct = _safe_number(_first(record, ("estimated_value", "contract_value", "tender_value", "value")))
    if direct is not None:
        return direct
    if profit is not None and margin and margin > 0:
        return round(profit / (margin / 100), 2)
    return None


def _readiness(record: Dict[str, Any], artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    pricing_schedule_found = _pricing_found(record, artifacts)
    boq_found = _has_artifact(artifacts, ("boq", "bill-of-quantity", "bill_of_quantity", "bill of quantity"))
    buyer_forms_found = bool(artifacts) or bool(record.get("document_paths"))
    sbd_forms_found = _has_artifact(artifacts, ("sbd", "standard-bidding", "standard bidding", "declaration"))

    missing_items: List[str] = []
    if not pricing_schedule_found:
        missing_items.append("pricing_schedule")
    if not boq_found:
        missing_items.append("boq")
    if not buyer_forms_found:
        missing_items.append("buyer_forms")
    if not sbd_forms_found:
        missing_items.append("sbd_forms")

    score = 0
    if pricing_schedule_found:
        score += 35
    if boq_found:
        score += 25
    if buyer_forms_found:
        score += 20
    if sbd_forms_found:
        score += 15
    if not missing_items:
        score += 5

    return {
        "quote_readiness_score": min(score, 100),
        "pricing_schedule_found": pricing_schedule_found,
        "boq_found": boq_found,
        "buyer_forms_found": buyer_forms_found,
        "sbd_forms_found": sbd_forms_found,
        "missing_items": missing_items,
    }


def _candidate_from_record(record: Dict[str, Any], artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    matched_artifacts = _artifacts_for_record(record, artifacts)
    readiness = _readiness(record, matched_artifacts)
    profit = _estimated_profit(record)
    margin = _margin_percent(record)
    value = _estimated_value(record, profit, margin)
    reference = _record_reference(record)
    title = _record_title(record)
    return {
        "id": _slug(reference) or _slug(title),
        "rfq_reference": reference,
        "title": title,
        "buyer": _safe_text(_first(record, ("buyer", "buyer_name", "department", "procuring_entity")), 220),
        "province": _safe_text(_first(record, ("province", "region", "location", "province_name")), 120),
        "source": _safe_text(_first(record, ("source", "portal", "portal_domain")), 220),
        "status": _safe_text(_first(record, ("current_state", "quote_status", "submission_status", "status")), 120),
        "estimated_value": value,
        "estimated_profit": profit,
        "margin_percent": margin,
        "readiness": readiness,
        "artifacts": {
            "buyer_docs": _filter_artifacts(matched_artifacts, ("buyer", "rfq", "tender", "form", "document")),
            "boqs": _filter_artifacts(matched_artifacts, ("boq", "bill-of-quantity", "bill_of_quantity", "bill of quantity")),
            "pricing_schedules": _filter_artifacts(matched_artifacts, ("pricing", "price", "schedule", "rates", "buyer_pricing")),
            "sbd_forms": _filter_artifacts(matched_artifacts, ("sbd", "standard-bidding", "standard bidding", "declaration")),
            "generated_quote_files": _filter_artifacts(matched_artifacts, ("quote", "lmcp", "pack")),
        },
        "latest_activity": _record_latest_activity(record),
        "recommended_next_step": _recommended_next_step(readiness["missing_items"]),
    }


def _recommended_next_step(missing_items: List[str]) -> str:
    if "pricing_schedule" in missing_items or "boq" in missing_items:
        return "Review pricing and BOQ artifacts before quote pack compilation"
    if "buyer_forms" in missing_items or "sbd_forms" in missing_items:
        return "Compile local placeholders and flag returnables for operator review"
    return "Generate local quote pack for operator review"


def _load_candidates(limit: Optional[int] = None) -> Dict[str, Any]:
    artifacts, sources_checked = _artifact_inventory()
    records = _load_rfq_records()
    candidates = [_candidate_from_record(record, artifacts) for record in records]
    candidates.sort(key=lambda item: item.get("latest_activity") or "", reverse=True)
    selected = candidates[: max(1, int(limit or DEFAULT_LIMIT))]
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "read_only": True,
        "safety": dict(SAFETY_FLAGS),
        "sources_checked": sources_checked,
        "items": selected,
        "count": len(selected),
        "total_candidates": len(candidates),
        "runtime_fallback_used": True,
    }


def _candidate_matches(candidate: Dict[str, Any], selector: str) -> bool:
    if not selector:
        return False
    selector_slug = _slug(selector)
    values = [
        candidate.get("id"),
        candidate.get("rfq_reference"),
        candidate.get("title"),
    ]
    for value in values:
        value_slug = _slug(value)
        if value_slug and (selector_slug == value_slug or selector_slug in value_slug or value_slug in selector_slug):
            return True
    return False


def _select_candidate(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    candidates = _load_candidates(limit=1000)["items"]
    selector = _safe_text(
        payload.get("id")
        or payload.get("candidate_id")
        or payload.get("rfq_reference")
        or payload.get("reference")
        or payload.get("rfq_id")
    )
    if not selector:
        return candidates[0] if candidates else None
    for candidate in candidates:
        if _candidate_matches(candidate, selector):
            return candidate
    return None


def _manifest_preview(candidate: Dict[str, Any], pack_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "pack_id": pack_id or f"DRY-RUN-{_safe_name(candidate.get('rfq_reference'), 'RFQ')}",
        "rfq_reference": candidate.get("rfq_reference"),
        "title": candidate.get("title"),
        "buyer": candidate.get("buyer"),
        "created_at": _now_iso(),
        "safety": dict(SAFETY_FLAGS),
        "readiness": candidate.get("readiness", {}),
        "files": [],
    }


def _safe_workspace(pack_id: str) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    workspace = (OUTPUT_ROOT / _safe_name(pack_id, "quote-pack")).resolve()
    root = OUTPUT_ROOT.resolve()
    if root not in workspace.parents and workspace != root:
        raise ValueError("Unsafe quote compilation workspace path")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _file_entry(path: Path, file_type: str) -> Dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {
        "name": path.name,
        "path": _relative(path),
        "type": file_type,
        "size_bytes": size,
    }


def _runtime_file_url(path: Path) -> Optional[str]:
    try:
        resolved = path.resolve()
        output_root = OUTPUT_ROOT.resolve()
        runtime_root = RUNTIME_DIR.resolve()
        if output_root not in resolved.parents and resolved != output_root:
            return None
        relative = resolved.relative_to(runtime_root)
        return f"/runtime/{relative.as_posix()}"
    except (OSError, ValueError):
        return None


def _pack_file_entry(path: Path, file_type: str) -> Dict[str, Any]:
    entry = _file_entry(path, file_type)
    entry["url"] = _runtime_file_url(path)
    return entry


def _safe_quote_pack_dir(pack_id: str) -> Optional[Path]:
    if not pack_id:
        return None
    try:
        root = OUTPUT_ROOT.resolve()
        candidate = (OUTPUT_ROOT / pack_id).resolve()
        if root not in candidate.parents and candidate != root:
            return None
        if not candidate.exists() or not candidate.is_dir():
            return None
        return candidate
    except OSError:
        return None


def _quote_pack_dirs() -> List[Path]:
    if not OUTPUT_ROOT.exists() or not OUTPUT_ROOT.is_dir():
        return []
    try:
        dirs = [path for path in OUTPUT_ROOT.iterdir() if path.is_dir() and not _contains_sensitive_marker(path)]
    except OSError:
        return []
    return sorted(dirs, key=lambda path: _modified_at(path), reverse=True)


def _safe_read_pack_json(workspace: Path, filename: str) -> Optional[Dict[str, Any]]:
    path = (workspace / filename).resolve()
    try:
        root = OUTPUT_ROOT.resolve()
        if root not in path.parents or path.parent != workspace.resolve():
            return None
    except OSError:
        return None
    data = _read_json(path)
    return data if isinstance(data, dict) else None


def _safe_read_pack_text(workspace: Path, filename: str) -> str:
    path = (workspace / filename).resolve()
    try:
        root = OUTPUT_ROOT.resolve()
        if root not in path.parents or path.parent != workspace.resolve():
            return ""
        if not path.exists() or not path.is_file() or _contains_sensitive_marker(path):
            return ""
        if path.stat().st_size > MAX_TEXT_PREVIEW_BYTES:
            return path.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_PREVIEW_BYTES]
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _pack_files(workspace: Path) -> List[Dict[str, Any]]:
    type_by_name = {
        "quote_summary.json": "quote_summary",
        "quote_pack_manifest.json": "quote_pack_manifest",
        "pricing_schedule_review.json": "pricing_schedule_review",
        "pricing_schedule_completed.json": "pricing_schedule_completed",
        "pricing_schedule_completed.csv": "pricing_schedule_completed_csv",
        "formal_quote_summary.json": "formal_quote_summary",
        "formal_quote_letter.txt": "formal_quote_letter",
        "quotation_cover_sheet.txt": "quotation_cover_sheet",
        "operator_quote_review.txt": "operator_quote_review",
        "returnables_checklist.json": "returnables_checklist",
        "returnables_completion.json": "returnables_completion",
        "returnables_completion_summary.txt": "returnables_completion_summary",
        "submission_binder_manifest.json": "submission_binder_manifest",
        "submission_binder_readiness.json": "submission_binder_readiness",
        "submission_binder_index.txt": "submission_binder_index",
        "operator_submission_binder_review.txt": "operator_submission_binder_review",
        "operator_next_steps.txt": "operator_next_steps",
        MANUAL_COMPLETION_FILENAME: "manual_completion",
        SUBMISSION_PROOF_FILENAME: "submission_proof",
    }
    files: List[Dict[str, Any]] = []
    try:
        for path in sorted(workspace.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file() or _contains_sensitive_marker(path):
                continue
            if path.suffix.lower() not in {".json", ".txt", ".csv"}:
                continue
            file_type = type_by_name.get(path.name, "placeholder" if path.name.startswith("placeholder_") else "local_pack_file")
            files.append(_pack_file_entry(path, file_type))
    except OSError:
        return files
    return files


def _pack_metadata(workspace: Path, manifest: Optional[Dict[str, Any]], files: List[Dict[str, Any]]) -> Dict[str, Any]:
    pack_id = workspace.name
    return {
        "pack_id": pack_id,
        "path": _relative(workspace),
        "url": _runtime_file_url(workspace),
        "created_at": _safe_text((manifest or {}).get("created_at") or _modified_at(workspace), 80),
        "modified_at": _modified_at(workspace),
        "rfq_reference": _safe_text((manifest or {}).get("rfq_reference"), 220),
        "title": _safe_text((manifest or {}).get("title"), 500),
        "buyer": _safe_text((manifest or {}).get("buyer"), 220),
        "file_count": len(files),
        "safety": dict(SAFETY_FLAGS),
    }


def _pack_detail(workspace: Path) -> Dict[str, Any]:
    manifest = _safe_read_pack_json(workspace, "quote_pack_manifest.json") or {}
    summary = _safe_read_pack_json(workspace, "quote_summary.json") or {}
    pricing_review = _safe_read_pack_json(workspace, "pricing_schedule_review.json") or {}
    returnables_checklist = _safe_read_pack_json(workspace, "returnables_checklist.json") or {}
    operator_next_steps = _safe_read_pack_text(workspace, "operator_next_steps.txt")
    files = _pack_files(workspace)
    metadata = _pack_metadata(workspace, manifest, files)
    return {
        "pack_id": workspace.name,
        "metadata": metadata,
        "manifest": manifest,
        "summary": summary,
        "pricing_schedule_review": pricing_review,
        "returnables_checklist": returnables_checklist,
        "operator_next_steps": operator_next_steps,
        "files": files,
        "read_only": True,
        "safety": dict(SAFETY_FLAGS),
    }


def _manual_completion_detail(workspace: Path) -> Dict[str, Any]:
    data = _safe_read_pack_json(workspace, MANUAL_COMPLETION_FILENAME)
    if not isinstance(data, dict):
        return {
            "status": "not_found",
            "message": "No manual completion record has been saved for this pack.",
            "pack_id": workspace.name,
            "manual_completion": None,
            "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
        }
    return {
        "status": "ok",
        "pack_id": workspace.name,
        "manual_completion": data,
        "saved_at": _safe_text(data.get("saved_at"), 80),
        "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
    }


def _money(value: float) -> float:
    return round(float(value or 0), 2)


def _pricing_number(value: Any, default: float = 0.0) -> float:
    number = _safe_number(value)
    if number is None:
        return default
    return float(number)


def _pack_pricing_context(workspace: Path) -> Dict[str, Any]:
    manifest = _safe_read_pack_json(workspace, "quote_pack_manifest.json") or {}
    summary = _safe_read_pack_json(workspace, "quote_summary.json") or {}
    return {
        "pack_id": workspace.name,
        "rfq_reference": _safe_text(manifest.get("rfq_reference") or summary.get("rfq_reference"), 220),
        "title": _safe_text(manifest.get("title") or summary.get("title"), 500),
        "buyer": _safe_text(manifest.get("buyer") or summary.get("buyer"), 220),
    }


def _placeholder_pricing_items(workspace: Path) -> List[Dict[str, Any]]:
    pricing_review = _safe_read_pack_json(workspace, "pricing_schedule_review.json") or {}
    sources = list(pricing_review.get("boqs") or []) + list(pricing_review.get("pricing_schedules") or [])
    descriptions = [
        _safe_text(source.get("name") or source.get("path"), 220)
        for source in sources
        if isinstance(source, dict) and _safe_text(source.get("name") or source.get("path"), 220)
    ]
    while len(descriptions) < 3:
        descriptions.append(f"Placeholder pricing line {len(descriptions) + 1}")
    return [
        {
            "line_no": index + 1,
            "description": description,
            "unit": "each",
            "quantity": 1,
            "unit_cost": 0,
            "markup_percent": DEFAULT_MARKUP_PERCENT,
            "pricing_status": "needs_review",
            "notes": "LOCAL PLACEHOLDER ONLY - replace with parsed BOQ/pricing data before operator approval.",
        }
        for index, description in enumerate(descriptions[:3])
    ]


def _pricing_payload_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidate = payload.get("items")
    if candidate is None and isinstance(payload.get("pricing"), dict):
        candidate = payload["pricing"].get("items")
    if not isinstance(candidate, list):
        return []
    return [item for item in candidate if isinstance(item, dict)]


def _calculate_pricing_model(
    workspace: Path,
    payload: Optional[Dict[str, Any]] = None,
    source: str = "calculated",
) -> Dict[str, Any]:
    payload = payload or {}
    context = _pack_pricing_context(workspace)
    saved_model = _safe_read_pack_json(workspace, "pricing_schedule_completed.json")
    raw_items = _pricing_payload_items(payload)
    if not raw_items and isinstance(saved_model, dict):
        raw_items = _pricing_payload_items(saved_model)
        if raw_items:
            source = "pricing_schedule_completed.json"
    placeholder_used = False
    if not raw_items:
        raw_items = _placeholder_pricing_items(workspace)
        placeholder_used = True
        source = "placeholder"

    currency = _safe_text(payload.get("currency") or (saved_model or {}).get("currency") or "ZAR", 12) or "ZAR"
    vat_rate = max(0.0, _pricing_number(payload.get("vat_rate") or (saved_model or {}).get("vat_rate"), DEFAULT_VAT_RATE))

    items: List[Dict[str, Any]] = []
    missing_prices: List[str] = []
    warnings: List[str] = []
    subtotal_ex_vat = 0.0
    vat_total = 0.0
    grand_total_inc_vat = 0.0
    estimated_profit = 0.0

    for index, raw in enumerate(raw_items, start=1):
        line_no = int(_pricing_number(raw.get("line_no"), index) or index)
        quantity = max(0.0, _pricing_number(raw.get("quantity"), 0.0))
        unit_cost = max(0.0, _pricing_number(raw.get("unit_cost"), 0.0))
        markup_percent = max(0.0, _pricing_number(raw.get("markup_percent"), DEFAULT_MARKUP_PERCENT))
        unit_price_ex_vat = _money(unit_cost * (1 + markup_percent / 100))
        total_ex_vat = _money(quantity * unit_price_ex_vat)
        vat_amount = _money(total_ex_vat * (vat_rate / 100))
        total_inc_vat = _money(total_ex_vat + vat_amount)
        explicit_status = _safe_text(raw.get("pricing_status"), 80).lower()
        pricing_status = explicit_status or ("priced" if quantity > 0 and unit_cost > 0 else "needs_review")
        if quantity <= 0 or unit_cost <= 0:
            pricing_status = "needs_review"
            missing_prices.append(f"line {line_no}: {_safe_text(raw.get('description'), 120) or 'missing price data'}")

        subtotal_ex_vat += total_ex_vat
        vat_total += vat_amount
        grand_total_inc_vat += total_inc_vat
        estimated_profit += _money((unit_price_ex_vat - unit_cost) * quantity)

        items.append(
            {
                "line_no": line_no,
                "description": _safe_text(raw.get("description"), 500) or f"Pricing line {line_no}",
                "unit": _safe_text(raw.get("unit"), 60) or "each",
                "quantity": quantity,
                "unit_cost": _money(unit_cost),
                "markup_percent": _money(markup_percent),
                "unit_price_ex_vat": unit_price_ex_vat,
                "total_ex_vat": total_ex_vat,
                "vat_amount": vat_amount,
                "total_inc_vat": total_inc_vat,
                "pricing_status": pricing_status,
                "notes": _safe_text(raw.get("notes"), 500),
            }
        )

    subtotal_ex_vat = _money(subtotal_ex_vat)
    vat_total = _money(vat_total)
    grand_total_inc_vat = _money(grand_total_inc_vat)
    estimated_profit = _money(estimated_profit)
    margin_percent = _money((estimated_profit / subtotal_ex_vat) * 100) if subtotal_ex_vat > 0 else 0.0

    if placeholder_used:
        warnings.append("No parsed BOQ/pricing schedule lines were found. Placeholder lines require operator review.")
    if missing_prices:
        warnings.append("One or more pricing lines are missing quantity or unit cost.")

    return {
        "pack_id": context["pack_id"],
        "rfq_reference": context["rfq_reference"],
        "currency": currency,
        "vat_rate": vat_rate,
        "items": items,
        "totals": {
            "subtotal_ex_vat": subtotal_ex_vat,
            "vat_total": vat_total,
            "grand_total_inc_vat": grand_total_inc_vat,
            "estimated_profit": estimated_profit,
            "margin_percent": margin_percent,
        },
        "missing_prices": missing_prices,
        "warnings": warnings,
        "source": source,
        "safety": dict(PRICING_SAFETY_FLAGS),
    }


def _write_pricing_csv(path: Path, pricing_model: Dict[str, Any]) -> None:
    fields = [
        "line_no",
        "description",
        "unit",
        "quantity",
        "unit_cost",
        "markup_percent",
        "unit_price_ex_vat",
        "total_ex_vat",
        "vat_amount",
        "total_inc_vat",
        "pricing_status",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in pricing_model.get("items", []):
            writer.writerow({field: item.get(field, "") for field in fields})


def _format_currency(value: Any, currency: str = "ZAR") -> str:
    return f"{currency} {_pricing_number(value, 0.0):,.2f}"


def _formal_quote_files(workspace: Path) -> List[Dict[str, Any]]:
    type_by_name = {
        "formal_quote_summary.json": "formal_quote_summary",
        "formal_quote_letter.txt": "formal_quote_letter",
        "quotation_cover_sheet.txt": "quotation_cover_sheet",
        "operator_quote_review.txt": "operator_quote_review",
    }
    files: List[Dict[str, Any]] = []
    for filename, file_type in type_by_name.items():
        path = workspace / filename
        if path.exists() and path.is_file() and not _contains_sensitive_marker(path):
            files.append(_pack_file_entry(path, file_type))
    return files


def _formal_quote_detail(workspace: Path) -> Dict[str, Any]:
    summary = _safe_read_pack_json(workspace, "formal_quote_summary.json")
    generated_files = _formal_quote_files(workspace)
    if not summary:
        return {
            "status": "not_found",
            "message": "No local formal quote has been generated for this pack.",
            "pack_id": workspace.name,
            "pricing_schedule_saved": (workspace / "pricing_schedule_completed.json").exists(),
            "generated_files": generated_files,
            "formal_quote_summary": None,
            "formal_quote_letter": "",
            "quotation_cover_sheet": "",
            "operator_quote_review": "",
            "safety": dict(PRICING_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }
    return {
        "status": "ok",
        "pack_id": workspace.name,
        "pricing_schedule_saved": True,
        "formal_quote_summary": summary,
        "formal_quote_letter": _safe_read_pack_text(workspace, "formal_quote_letter.txt"),
        "quotation_cover_sheet": _safe_read_pack_text(workspace, "quotation_cover_sheet.txt"),
        "operator_quote_review": _safe_read_pack_text(workspace, "operator_quote_review.txt"),
        "generated_files": generated_files,
        "safety": dict(PRICING_SAFETY_FLAGS),
        "timestamp": _now_iso(),
    }


def _write_formal_quote_files(workspace: Path, pricing: Dict[str, Any]) -> Dict[str, Any]:
    context = _pack_pricing_context(workspace)
    manifest = _safe_read_pack_json(workspace, "quote_pack_manifest.json") or {}
    returnables = _safe_read_pack_json(workspace, "returnables_checklist.json") or {}
    totals = pricing.get("totals") or {}
    currency = _safe_text(pricing.get("currency"), 12) or "ZAR"
    created_at = _now_iso()
    validity_days = 30
    missing_items = returnables.get("missing_items") or manifest.get("readiness", {}).get("missing_items") or []

    summary: Dict[str, Any] = {
        "pack_id": workspace.name,
        "rfq_reference": context["rfq_reference"],
        "title": context["title"],
        "buyer": context["buyer"],
        "created_at": created_at,
        "currency": currency,
        "subtotal_ex_vat": _money(totals.get("subtotal_ex_vat", 0)),
        "vat_total": _money(totals.get("vat_total", 0)),
        "grand_total_inc_vat": _money(totals.get("grand_total_inc_vat", 0)),
        "estimated_profit": _money(totals.get("estimated_profit", 0)),
        "margin_percent": _money(totals.get("margin_percent", 0)),
        "validity_days": validity_days,
        "safety": dict(PRICING_SAFETY_FLAGS),
        "generated_files": [],
    }

    letter_path = workspace / "formal_quote_letter.txt"
    letter_path.write_text(
        "\n".join(
            [
                "FORMAL QUOTE LETTER",
                "LOCAL QUOTE ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED",
                "",
                f"Date: {created_at}",
                f"Buyer: {context['buyer'] or 'Unknown Buyer'}",
                f"RFQ Reference: {context['rfq_reference'] or workspace.name}",
                f"Title: {context['title'] or 'Untitled quote'}",
                "",
                "Quote totals:",
                f"- Subtotal ex VAT: {_format_currency(summary['subtotal_ex_vat'], currency)}",
                f"- VAT: {_format_currency(summary['vat_total'], currency)}",
                f"- Total inc VAT: {_format_currency(summary['grand_total_inc_vat'], currency)}",
                "",
                f"This local quote is valid for {validity_days} days from the generated date.",
                "Operator must review pricing, returnables, and buyer requirements before any separate manual submission process.",
            ]
        ),
        encoding="utf-8",
    )

    cover_path = workspace / "quotation_cover_sheet.txt"
    cover_path.write_text(
        "\n".join(
            [
                "QUOTATION COVER SHEET",
                "LOCAL QUOTE ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED",
                "",
                f"Pack ID: {workspace.name}",
                f"RFQ Reference: {context['rfq_reference'] or workspace.name}",
                f"Buyer: {context['buyer'] or 'Unknown Buyer'}",
                f"Title: {context['title'] or 'Untitled quote'}",
                f"Currency: {currency}",
                f"Grand Total inc VAT: {_format_currency(summary['grand_total_inc_vat'], currency)}",
                f"Estimated Profit: {_format_currency(summary['estimated_profit'], currency)}",
                f"Margin Percent: {summary['margin_percent']}%",
            ]
        ),
        encoding="utf-8",
    )

    review_path = workspace / "operator_quote_review.txt"
    review_path.write_text(
        "\n".join(
            [
                "OPERATOR QUOTE REVIEW",
                "LOCAL QUOTE ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED",
                "",
                "Required operator checks:",
                "- Confirm pricing schedule values and VAT calculation.",
                "- Confirm buyer forms and SBD returnables are complete.",
                "- Confirm the quote letter and cover sheet match buyer requirements.",
                "- Do not submit, email, or upload this pack from the autonomous system.",
                "",
                "Missing returnables or readiness items:",
                *(f"- {_safe_text(item, 160)}" for item in missing_items),
            ]
        ),
        encoding="utf-8",
    )

    summary_path = workspace / "formal_quote_summary.json"
    _write_json(summary_path, summary)
    summary["generated_files"] = _formal_quote_files(workspace)
    _write_json(summary_path, summary)
    return summary


def _returnable_status(value: Any, default: str = "missing") -> str:
    status = _safe_text(value, 80).lower().replace(" ", "_").replace("-", "_")
    return status if status in RETURNABLE_STATUSES else default


def _returnable_id(name: Any, category: str) -> str:
    return _slug(f"{category}-{name}") or _safe_name(f"{category}-{name}", "returnable").lower()


def _normalize_returnable_item(raw: Any, fallback_name: str, category: str) -> Dict[str, Any]:
    record = raw if isinstance(raw, dict) else {}
    name = _safe_text(record.get("name") or record.get("title") or record.get("label") or fallback_name, 180)
    return {
        "id": _safe_text(record.get("id"), 120) or _returnable_id(name, category),
        "name": name,
        "category": _safe_text(record.get("category"), 80) or category,
        "required": bool(record.get("required", True)),
        "status": _returnable_status(record.get("status"), "missing"),
        "source_file": _safe_text(record.get("source_file") or record.get("source") or record.get("path"), 500),
        "notes": _safe_text(record.get("notes"), 700),
    }


def _normalize_sbd_item(raw: Any, fallback_form: str) -> Dict[str, Any]:
    record = raw if isinstance(raw, dict) else {}
    form = _safe_text(record.get("form") or record.get("name") or fallback_form, 80)
    return {
        "form": form,
        "required": bool(record.get("required", True)),
        "status": _returnable_status(record.get("status"), "missing"),
        "source_file": _safe_text(record.get("source_file") or record.get("source") or record.get("path"), 500),
        "notes": _safe_text(record.get("notes"), 700),
    }


def _normalize_company_document(raw: Any, fallback_name: str) -> Dict[str, Any]:
    record = raw if isinstance(raw, dict) else {}
    name = _safe_text(record.get("name") or record.get("title") or fallback_name, 180)
    return {
        "name": name,
        "required": bool(record.get("required", True)),
        "status": _returnable_status(record.get("status"), "missing"),
        "source_file": _safe_text(record.get("source_file") or record.get("source") or record.get("path"), 500),
        "notes": _safe_text(record.get("notes"), 700),
    }


def _completion_counts(
    returnables: List[Dict[str, Any]],
    sbd_forms: List[Dict[str, Any]],
    company_documents: List[Dict[str, Any]],
) -> Dict[str, Any]:
    rows = [*returnables, *sbd_forms, *company_documents]
    required = [row for row in rows if row.get("required", True)]
    required_count = len(required)
    completed_count = sum(1 for row in required if row.get("status") in {"completed", "not_applicable"})
    missing_count = sum(1 for row in required if row.get("status") == "missing")
    needs_review_count = sum(1 for row in required if row.get("status") == "needs_review")
    completion_score = round((completed_count / required_count) * 100) if required_count else 100
    return {
        "required_count": required_count,
        "completed_count": completed_count,
        "missing_count": missing_count,
        "needs_review_count": needs_review_count,
        "completion_score": completion_score,
    }


def _seed_returnables_model(workspace: Path) -> Dict[str, Any]:
    context = _pack_pricing_context(workspace)
    pricing_path = workspace / "pricing_schedule_completed.json"
    formal_quote_path = workspace / "formal_quote_letter.txt"
    checklist = _safe_read_pack_json(workspace, "returnables_checklist.json") or {}
    sbd_sources = checklist.get("sbd_forms") if isinstance(checklist.get("sbd_forms"), list) else []

    returnables = [
        _normalize_returnable_item(
            {
                "name": "Signed quotation",
                "status": "available" if formal_quote_path.exists() else "needs_review",
                "source_file": _relative(formal_quote_path) if formal_quote_path.exists() else "",
                "notes": "Track signature status locally. Do not generate official signature/legal documents here.",
            },
            "Signed quotation",
            "quote_returnable",
        ),
        _normalize_returnable_item(
            {
                "name": "Completed pricing schedule",
                "status": "completed" if pricing_path.exists() else "missing",
                "source_file": _relative(pricing_path) if pricing_path.exists() else "",
                "notes": "Generated locally from pricing schedule completion layer.",
            },
            "Completed pricing schedule",
            "pricing",
        ),
    ]
    company_documents = [
        _normalize_company_document({}, "CSD registration report"),
        _normalize_company_document({}, "Tax compliance status/PIN"),
        _normalize_company_document({}, "BBBEE affidavit/certificate"),
        _normalize_company_document({}, "Company registration documents"),
        _normalize_company_document({}, "Director ID copy"),
    ]
    sbd_forms: List[Dict[str, Any]] = []
    for form in SBD_FORM_NAMES:
        source = ""
        for item in sbd_sources:
            if isinstance(item, dict) and form.lower().replace(" ", "") in f"{item.get('name', '')} {item.get('path', '')}".lower().replace(" ", ""):
                source = _safe_text(item.get("path") or item.get("name"), 500)
                break
        sbd_forms.append(
            _normalize_sbd_item(
                {
                    "form": form,
                    "status": "available" if source else "missing",
                    "source_file": source,
                    "notes": "Local tracking only. Official SBD completion remains an operator/legal review task.",
                },
                form,
            )
        )

    return {
        "pack_id": workspace.name,
        "rfq_reference": context["rfq_reference"],
        "title": context["title"],
        "buyer": context["buyer"],
        "updated_at": _now_iso(),
        "returnables": returnables,
        "sbd_forms": sbd_forms,
        "company_documents": company_documents,
        "completion": _completion_counts(returnables, sbd_forms, company_documents),
        "safety": dict(PRICING_SAFETY_FLAGS),
    }


def _normalize_returnables_model(workspace: Path, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = _pack_pricing_context(workspace)
    source = payload if isinstance(payload, dict) else None
    if source is None:
        saved = _safe_read_pack_json(workspace, "returnables_completion.json")
        source = saved if isinstance(saved, dict) else None
    if source is None:
        return _seed_returnables_model(workspace)

    returnables_raw = source.get("returnables") if isinstance(source.get("returnables"), list) else []
    sbd_raw = source.get("sbd_forms") if isinstance(source.get("sbd_forms"), list) else []
    company_raw = source.get("company_documents") if isinstance(source.get("company_documents"), list) else []
    seeded = _seed_returnables_model(workspace)

    returnables = [
        _normalize_returnable_item(item, seeded["returnables"][index]["name"] if index < len(seeded["returnables"]) else "Returnable", "returnable")
        for index, item in enumerate(returnables_raw or seeded["returnables"])
    ]
    sbd_forms = [
        _normalize_sbd_item(item, seeded["sbd_forms"][index]["form"] if index < len(seeded["sbd_forms"]) else "SBD")
        for index, item in enumerate(sbd_raw or seeded["sbd_forms"])
    ]
    company_documents = [
        _normalize_company_document(item, seeded["company_documents"][index]["name"] if index < len(seeded["company_documents"]) else "Company document")
        for index, item in enumerate(company_raw or seeded["company_documents"])
    ]

    return {
        "pack_id": workspace.name,
        "rfq_reference": _safe_text(source.get("rfq_reference") or context["rfq_reference"], 220),
        "title": _safe_text(source.get("title") or context["title"], 500),
        "buyer": _safe_text(source.get("buyer") or context["buyer"], 220),
        "updated_at": _safe_text(source.get("updated_at"), 80) or _now_iso(),
        "returnables": returnables,
        "sbd_forms": sbd_forms,
        "company_documents": company_documents,
        "completion": _completion_counts(returnables, sbd_forms, company_documents),
        "safety": dict(PRICING_SAFETY_FLAGS),
    }


def _write_returnables_summary(path: Path, model: Dict[str, Any]) -> None:
    completion = model.get("completion") or {}
    lines = [
        "RETURNABLES COMPLETION SUMMARY",
        "LOCAL RETURNABLES REVIEW ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED",
        "",
        f"Pack ID: {model.get('pack_id')}",
        f"RFQ Reference: {model.get('rfq_reference')}",
        f"Buyer: {model.get('buyer')}",
        f"Updated at: {model.get('updated_at')}",
        "",
        f"Required count: {completion.get('required_count')}",
        f"Completed count: {completion.get('completed_count')}",
        f"Missing count: {completion.get('missing_count')}",
        f"Needs review count: {completion.get('needs_review_count')}",
        f"Completion score: {completion.get('completion_score')}%",
        "",
        "Items requiring attention:",
    ]
    for section in ("returnables", "sbd_forms", "company_documents"):
        for item in model.get(section, []):
            if item.get("required", True) and item.get("status") in {"missing", "needs_review"}:
                label = item.get("name") or item.get("form") or "Returnable"
                lines.append(f"- {label}: {item.get('status')} {item.get('notes') or ''}".strip())
    path.write_text("\n".join(lines), encoding="utf-8")


def _submission_binder_files(workspace: Path) -> List[Dict[str, Any]]:
    type_by_name = {
        "submission_binder_manifest.json": "submission_binder_manifest",
        "submission_binder_readiness.json": "submission_binder_readiness",
        "submission_binder_index.txt": "submission_binder_index",
        "operator_submission_binder_review.txt": "operator_submission_binder_review",
    }
    files: List[Dict[str, Any]] = []
    for filename, file_type in type_by_name.items():
        path = workspace / filename
        if path.exists() and path.is_file() and not _contains_sensitive_marker(path):
            files.append(_pack_file_entry(path, file_type))
    return files


def _submission_binder_source_files(workspace: Path) -> List[Dict[str, Any]]:
    binder_types = {
        "submission_binder_manifest",
        "submission_binder_readiness",
        "submission_binder_index",
        "operator_submission_binder_review",
    }
    return [file for file in _pack_files(workspace) if file.get("type") not in binder_types]


def _submission_binder_readiness(workspace: Path) -> Dict[str, Any]:
    pricing_completed = (workspace / "pricing_schedule_completed.json").exists()
    formal_quote_generated = (workspace / "formal_quote_summary.json").exists()
    returnables_review_completed = (workspace / "returnables_completion.json").exists()
    missing_items: List[str] = []
    blockers: List[str] = []

    if not pricing_completed:
        missing_items.append("pricing_schedule_completed.json")
        blockers.append("Pricing schedule must be saved locally before binder readiness is complete.")
    if not formal_quote_generated:
        missing_items.append("formal_quote_summary.json")
        blockers.append("Formal quote must be generated locally before binder readiness is complete.")
    if not returnables_review_completed:
        missing_items.append("returnables_completion.json")
        blockers.append("Returnables review must be saved locally before binder readiness is complete.")

    if returnables_review_completed:
        returnables_model = _normalize_returnables_model(workspace)
        completion = returnables_model.get("completion") or {}
        missing_count = int(completion.get("missing_count") or 0)
        needs_review_count = int(completion.get("needs_review_count") or 0)
        if missing_count:
            missing_items.append(f"{missing_count} required returnables missing")
            blockers.append("Returnables review still has required missing items.")
        if needs_review_count:
            missing_items.append(f"{needs_review_count} returnables need review")
            blockers.append("Returnables review still has items marked needs_review.")

    score = 0
    if pricing_completed:
        score += 30
    if formal_quote_generated:
        score += 30
    if returnables_review_completed:
        score += 25
    if not missing_items and not blockers:
        score += 15

    return {
        "submission_binder_score": min(score, 100),
        "pricing_completed": pricing_completed,
        "formal_quote_generated": formal_quote_generated,
        "returnables_review_completed": returnables_review_completed,
        "missing_items": missing_items,
        "blockers": blockers,
    }


def _submission_binder_manifest(workspace: Path, created_at: Optional[str] = None) -> Dict[str, Any]:
    context = _pack_pricing_context(workspace)
    return {
        "pack_id": workspace.name,
        "rfq_reference": context["rfq_reference"],
        "title": context["title"],
        "buyer": context["buyer"],
        "created_at": created_at or _now_iso(),
        "readiness": _submission_binder_readiness(workspace),
        "binder_files": _submission_binder_files(workspace),
        "source_files": _submission_binder_source_files(workspace),
        "safety": dict(BINDER_SAFETY_FLAGS),
    }


def _submission_binder_detail(workspace: Path) -> Dict[str, Any]:
    manifest = _safe_read_pack_json(workspace, "submission_binder_manifest.json")
    readiness = _safe_read_pack_json(workspace, "submission_binder_readiness.json")
    if isinstance(readiness, dict) and isinstance(readiness.get("readiness"), dict):
        readiness = readiness["readiness"]
    if not isinstance(readiness, dict):
        readiness = _submission_binder_readiness(workspace)
    generated = bool(manifest)
    return {
        "status": "ok" if generated else "not_found",
        "message": "" if generated else "No local submission binder has been generated for this pack.",
        "pack_id": workspace.name,
        "submission_binder_manifest": manifest,
        "readiness": readiness,
        "binder_files": _submission_binder_files(workspace),
        "source_files": _submission_binder_source_files(workspace),
        "submission_binder_index": _safe_read_pack_text(workspace, "submission_binder_index.txt"),
        "operator_submission_binder_review": _safe_read_pack_text(workspace, "operator_submission_binder_review.txt"),
        "safety": dict(BINDER_SAFETY_FLAGS),
        "timestamp": _now_iso(),
    }


def _submission_binder_list_item(workspace: Path) -> Optional[Dict[str, Any]]:
    detail = _submission_binder_detail(workspace)
    if detail.get("status") != "ok":
        return None

    manifest = detail.get("submission_binder_manifest")
    if not isinstance(manifest, dict):
        manifest = {}
    readiness = detail.get("readiness") or manifest.get("readiness") or {}
    if not isinstance(readiness, dict):
        readiness = {}

    context = _pack_pricing_context(workspace)
    return {
        "pack_id": workspace.name,
        "rfq_reference": _safe_text(manifest.get("rfq_reference") or context["rfq_reference"], 220),
        "title": _safe_text(manifest.get("title") or context["title"], 500),
        "buyer": _safe_text(manifest.get("buyer") or context["buyer"], 220),
        "created_at": _safe_text(manifest.get("created_at") or _modified_at(workspace), 80),
        "submission_binder_score": int(_safe_number(readiness.get("submission_binder_score")) or 0),
        "pricing_completed": bool(readiness.get("pricing_completed")),
        "formal_quote_generated": bool(readiness.get("formal_quote_generated")),
        "returnables_review_completed": bool(readiness.get("returnables_review_completed")),
        "missing_items": [
            _safe_text(item, 220)
            for item in readiness.get("missing_items", [])
            if _safe_text(item, 220)
        ],
        "blockers": [
            _safe_text(item, 260)
            for item in readiness.get("blockers", [])
            if _safe_text(item, 260)
        ],
        "binder_files": detail.get("binder_files", []),
        "source_files": detail.get("source_files", []),
        "safety": dict(BINDER_SAFETY_FLAGS),
    }


def _submission_binder_gate_message(
    matched_binder: Optional[Dict[str, Any]],
    can_prepare_submission: bool,
    blockers: List[str],
    missing_returnables: List[str],
    manual_completion: Optional[Dict[str, Any]] = None,
) -> str:
    if isinstance(manual_completion, dict) and not manual_completion.get("allowed", False):
        return _safe_text(
            manual_completion.get("blocked_reason"),
            500,
        ) or "Manual completion record is required before final submission."
    if not matched_binder:
        return "No generated local submission binder matched this pack. Final submission is blocked by design. Manual upload only."
    if can_prepare_submission:
        return "Local binder is ready for operator submission preparation review. Final submission is blocked by design. Manual upload only."
    if blockers or missing_returnables:
        return "Local binder has blockers or missing returnables. Final submission is blocked by design. Manual upload only."
    return "Local binder is not ready for submission preparation. Final submission is blocked by design. Manual upload only."


def get_submission_binder_gate(pack_id: str, rfq_reference: str | None = None) -> Dict[str, Any]:
    safe_pack_id = _safe_text(pack_id, 220)
    requested_reference = _safe_text(rfq_reference, 220)
    workspace = _safe_quote_pack_dir(safe_pack_id)
    matched_binder: Optional[Dict[str, Any]] = None
    manual_completion: Dict[str, Any] = {
        "required": True,
        "allowed": False,
        "blocked_reason": "Manual completion record is required before final submission.",
        "reason_code": "manual_completion_missing",
        "status": "missing",
        "manual_completion": None,
        "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
    }

    if workspace:
        matched_binder = _submission_binder_list_item(workspace)
        manual_completion = _manual_completion_gate(workspace)

    if not matched_binder and requested_reference:
        reference_slug = _slug(requested_reference)
        for candidate in _quote_pack_dirs():
            item = _submission_binder_list_item(candidate)
            if item and reference_slug and _slug(item.get("rfq_reference")) == reference_slug:
                matched_binder = item
                workspace = candidate
                manual_completion = _manual_completion_gate(candidate)
                break

    if matched_binder and requested_reference:
        binder_reference = _slug(matched_binder.get("rfq_reference"))
        if binder_reference and binder_reference != _slug(requested_reference):
            matched_binder = None

    binder_score = int((matched_binder or {}).get("submission_binder_score") or 0)
    blockers = list((matched_binder or {}).get("blockers") or [])
    missing_items = list((matched_binder or {}).get("missing_items") or [])
    missing_returnables = [
        _safe_text(item, 220)
        for item in missing_items
        if re.search(r"returnable|sbd|company|document|form", _safe_text(item, 220), re.IGNORECASE)
    ]
    can_prepare_submission = bool(matched_binder) and binder_score >= 85 and not blockers and not missing_returnables

    return {
        "status": "ok" if matched_binder else "not_found",
        "pack_id": (workspace.name if workspace else safe_pack_id),
        "rfq_reference": _safe_text((matched_binder or {}).get("rfq_reference") or requested_reference, 220),
        "can_prepare_submission": can_prepare_submission,
        "can_submit_final": bool(can_prepare_submission and manual_completion.get("allowed")),
        "manual_completion_required": True,
        "manual_completion": manual_completion,
        "manual_completion_allowed": bool(manual_completion.get("allowed")),
        "manual_completion_blocked_reason": _safe_text(manual_completion.get("blocked_reason"), 500),
        "binder_score": binder_score,
        "blockers": blockers,
        "missing_returnables": missing_returnables,
        "safety_flags": dict(BINDER_SAFETY_FLAGS),
        "matched_binder": matched_binder,
        "message": _submission_binder_gate_message(matched_binder, can_prepare_submission, blockers, missing_returnables, manual_completion),
    }


def _manual_upload_steps(gate: Dict[str, Any]) -> List[str]:
    return [
        "Review the local submission binder and confirm all source files are current.",
        "Resolve all listed blockers and missing returnables before manual upload.",
        "Open the buyer portal manually using an operator-controlled browser session.",
        "Upload the approved local binder files manually according to buyer instructions.",
        "Capture portal confirmation, screenshots, or receipt proof after manual upload.",
        "Store proof artifacts in the proof centre or approved local evidence folder.",
        "Do not use autonomous final submit, portal upload, email sending, or CAPTCHA bypass from this system.",
    ]


def _submission_gate_checklist_text(checklist: Dict[str, Any]) -> str:
    manual_completion = checklist.get("manual_completion") if isinstance(checklist.get("manual_completion"), dict) else {}
    lines = [
        "MANUAL SUBMISSION CHECKLIST",
        "READ ONLY - LOCAL BINDER REVIEW - FINAL SUBMIT LOCKED",
        "",
        f"Pack ID: {checklist.get('pack_id') or ''}",
        f"RFQ Reference: {checklist.get('rfq_reference') or ''}",
        f"Binder Score: {checklist.get('binder_score')}",
        f"Manual Completion: {manual_completion.get('status') or 'missing'}",
        f"Manual Completion Allowed: {manual_completion.get('allowed')}",
        "",
        "Missing returnables:",
    ]
    missing_returnables = checklist.get("missing_returnables") or []
    lines.extend(f"- {_safe_text(item, 220)}" for item in missing_returnables)
    if not missing_returnables:
        lines.append("- None reported by the gate.")

    lines.extend(["", "Blockers:"])
    blockers = checklist.get("blockers") or []
    lines.extend(f"- {_safe_text(item, 260)}" for item in blockers)
    if not blockers:
        lines.append("- None reported by the gate.")

    lines.extend(["", "Manual upload steps:"])
    lines.extend(f"{index}. {_safe_text(step, 300)}" for index, step in enumerate(checklist.get("manual_upload_steps") or [], start=1))
    lines.extend(
        [
            "",
            f"Final submit warning: {checklist.get('final_submit_warning')}",
            "",
            "Safety flags:",
        ]
    )
    safety_flags = checklist.get("safety_flags") or {}
    if isinstance(safety_flags, dict):
        lines.extend(f"- {key}: {value}" for key, value in safety_flags.items())
    return "\n".join(lines)


def get_submission_binder_gate_checklist(
    pack_id: str,
    rfq_reference: str | None = None,
    include_text: bool = True,
) -> Dict[str, Any]:
    gate = get_submission_binder_gate(pack_id, rfq_reference)
    final_submit_warning = "Final submission is blocked by design. Manual upload only."
    checklist: Dict[str, Any] = {
        "status": gate.get("status"),
        "pack_id": gate.get("pack_id"),
        "rfq_reference": gate.get("rfq_reference"),
        "binder_score": gate.get("binder_score", 0),
        "missing_returnables": gate.get("missing_returnables", []),
        "blockers": gate.get("blockers", []),
        "safety_flags": gate.get("safety_flags", dict(BINDER_SAFETY_FLAGS)),
        "manual_completion_required": True,
        "manual_completion": gate.get("manual_completion"),
        "manual_completion_allowed": gate.get("manual_completion_allowed", False),
        "manual_completion_blocked_reason": gate.get("manual_completion_blocked_reason", ""),
        "manual_upload_steps": _manual_upload_steps(gate),
        "final_submit_warning": gate.get("manual_completion_blocked_reason") or final_submit_warning,
        "can_submit_final": False,
        "message": gate.get("message") or gate.get("manual_completion_blocked_reason") or final_submit_warning,
    }
    if include_text:
        checklist["checklist_text"] = _submission_gate_checklist_text(checklist)
    return checklist


def _submission_gate_readiness_status(gate: Dict[str, Any]) -> str:
    manual_completion = gate.get("manual_completion") if isinstance(gate.get("manual_completion"), dict) else {}
    if manual_completion and manual_completion.get("allowed") is False:
        return "manual_completion_required"
    if manual_completion and manual_completion.get("allowed") is True:
        if gate.get("can_prepare_submission") is True:
            return "ready_for_manual_submission"
        return "manual_completion_recorded"
    if gate.get("status") != "ok":
        return "binder_not_found"
    if gate.get("can_prepare_submission") is True:
        return "ready_for_manual_preparation"
    if gate.get("blockers") or gate.get("missing_returnables"):
        return "blocked"
    if int(gate.get("binder_score") or 0) >= 85:
        return "review_required"
    return "incomplete"


def _submission_gate_audit_event(
    timestamp: str,
    event_type: str,
    status: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "timestamp": timestamp,
        "event_type": event_type,
        "status": status,
        "message": _safe_text(message, 500),
        "details": details or {},
    }


def _submission_gate_audit_events(gate: Dict[str, Any], checklist: Dict[str, Any], generated_at: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    matched_binder = gate.get("matched_binder")
    if isinstance(matched_binder, dict):
        binder_time = _safe_text(matched_binder.get("created_at"), 80) or generated_at
        events.append(
            _submission_gate_audit_event(
                binder_time,
                "binder_detected",
                "ok",
                "Local submission binder metadata detected.",
                {"pack_id": matched_binder.get("pack_id"), "rfq_reference": matched_binder.get("rfq_reference")},
            )
        )
        readiness_checks = (
            ("pricing_completed", "Pricing schedule completion recorded."),
            ("formal_quote_generated", "Formal quote generation recorded."),
            ("returnables_review_completed", "Returnables review recorded."),
        )
        for key, message in readiness_checks:
            complete = bool(matched_binder.get(key))
            events.append(
                _submission_gate_audit_event(
                    binder_time,
                    key,
                    "ok" if complete else "missing",
                    message if complete else f"{message} Status requires review.",
                {"value": complete},
            )
        )
    else:
        events.append(
            _submission_gate_audit_event(
                generated_at,
                "binder_not_found",
                "blocked",
                "No local submission binder metadata matched this pack.",
            )
        )

    manual_completion = gate.get("manual_completion") if isinstance(gate.get("manual_completion"), dict) else {}
    if manual_completion:
        events.append(
            _submission_gate_audit_event(
                _safe_text(manual_completion.get("saved_at"), 80) or generated_at,
                "manual_completion_gate",
                "ok" if manual_completion.get("allowed") else "blocked",
                manual_completion.get("blocked_reason") or "Manual completion record validated.",
                {
                    "allowed": bool(manual_completion.get("allowed")),
                    "reason_code": manual_completion.get("reason_code"),
                    "missing_fields": manual_completion.get("missing_fields", []),
                    "forbidden_fields": manual_completion.get("forbidden_fields", []),
                },
            )
        )

    for item in gate.get("blockers") or []:
        events.append(
            _submission_gate_audit_event(
                generated_at,
                "blocker_detected",
                "blocked",
                _safe_text(item, 260),
            )
        )
    for item in gate.get("missing_returnables") or []:
        events.append(
            _submission_gate_audit_event(
                generated_at,
                "missing_returnable_detected",
                "blocked",
                _safe_text(item, 220),
            )
        )

    checklist_available = bool(checklist.get("checklist_text"))
    events.append(
        _submission_gate_audit_event(
            generated_at,
            "manual_checklist_export",
            "available" if checklist_available else "unavailable",
            "Manual checklist text export metadata evaluated.",
            {"checklist_download_available": checklist_available},
        )
    )
    events.append(
        _submission_gate_audit_event(
            generated_at,
            "final_submit_lock",
            "locked",
            "Final submit remains locked by design. Manual upload only.",
            {"final_submit_locked": True},
        )
    )
    return events


def get_submission_binder_gate_audit_log(
    pack_id: str,
    rfq_reference: str | None = None,
) -> Dict[str, Any]:
    gate = get_submission_binder_gate(pack_id, rfq_reference)
    checklist = get_submission_binder_gate_checklist(pack_id, rfq_reference, include_text=True)
    matched_binder = gate.get("matched_binder")
    generated_at = ""
    if isinstance(matched_binder, dict):
        generated_at = _safe_text(matched_binder.get("created_at"), 80)
    generated_at = generated_at or _now_iso()
    readiness_status = _submission_gate_readiness_status(gate)
    return {
        "status": gate.get("status"),
        "pack_id": gate.get("pack_id"),
        "rfq_reference": gate.get("rfq_reference"),
        "generated_at": generated_at,
        "binder_score": gate.get("binder_score", 0),
        "readiness_status": readiness_status,
        "blockers": gate.get("blockers", []),
        "missing_returnables": gate.get("missing_returnables", []),
        "manual_completion_required": True,
        "manual_completion": gate.get("manual_completion"),
        "manual_completion_allowed": gate.get("manual_completion_allowed", False),
        "manual_completion_blocked_reason": gate.get("manual_completion_blocked_reason", ""),
        "safety_flags": gate.get("safety_flags", dict(BINDER_SAFETY_FLAGS)),
        "checklist_download_available": bool(checklist.get("checklist_text")),
        "final_submit_locked": True,
        "events": _submission_gate_audit_events(gate, checklist, generated_at),
    }


def _submission_gate_audit_log_text(audit_log: Dict[str, Any]) -> str:
    lines = [
        "SUBMISSION AUDIT LOG",
        "READ ONLY - LOCAL BINDER REVIEW - FINAL SUBMIT LOCKED",
        "",
        f"Pack ID: {audit_log.get('pack_id') or ''}",
        f"RFQ Reference: {audit_log.get('rfq_reference') or ''}",
        f"Generated at: {audit_log.get('generated_at') or ''}",
        f"Binder score: {audit_log.get('binder_score')}",
        f"Readiness status: {audit_log.get('readiness_status') or ''}",
        f"Checklist download available: {audit_log.get('checklist_download_available')}",
        f"Final submit locked: {audit_log.get('final_submit_locked')}",
        "",
        "Blockers:",
    ]
    blockers = audit_log.get("blockers") or []
    lines.extend(f"- {_safe_text(item, 260)}" for item in blockers)
    if not blockers:
        lines.append("- None reported by the gate.")

    lines.extend(["", "Missing returnables:"])
    missing_returnables = audit_log.get("missing_returnables") or []
    lines.extend(f"- {_safe_text(item, 220)}" for item in missing_returnables)
    if not missing_returnables:
        lines.append("- None reported by the gate.")

    lines.extend(["", "Safety flags:"])
    safety_flags = audit_log.get("safety_flags") or {}
    if isinstance(safety_flags, dict):
        lines.extend(f"- {key}: {value}" for key, value in safety_flags.items())

    lines.extend(["", "Events:"])
    for index, event in enumerate(audit_log.get("events") or [], start=1):
        if not isinstance(event, dict):
            continue
        lines.extend(
            [
                f"{index}. [{_safe_text(event.get('timestamp'), 80)}] {_safe_text(event.get('event_type'), 120)} - {_safe_text(event.get('status'), 80)}",
                f"   {_safe_text(event.get('message'), 500)}",
            ]
        )
    if not audit_log.get("events"):
        lines.append("- No audit events available.")

    lines.extend(["", "Final submission is blocked by design. Manual upload only."])
    return "\n".join(lines)


def _safe_evidence_file_entry(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    raw_url = _safe_text(raw.get("url"), 700)
    raw_path = _safe_text(raw.get("path"), 700)
    safe_url = ""
    if raw_url.startswith("/runtime/quote_compilation/"):
        safe_url = raw_url
    elif raw_path.startswith("/runtime/quote_compilation/"):
        safe_url = raw_path
    elif raw_path.startswith("runtime/quote_compilation/"):
        safe_url = f"/{raw_path}"
    if not safe_url:
        return None
    return {
        "name": _safe_text(raw.get("name"), 220) or Path(safe_url).name,
        "type": _safe_text(raw.get("type"), 120) or "evidence_file",
        "path": safe_url,
        "url": safe_url,
        "size_bytes": int(_safe_number(raw.get("size_bytes")) or 0),
    }


def _submission_gate_evidence_files(matched_binder: Any) -> List[Dict[str, Any]]:
    if not isinstance(matched_binder, dict):
        return []
    raw_files = list(matched_binder.get("binder_files") or []) + list(matched_binder.get("source_files") or [])
    files: List[Dict[str, Any]] = []
    seen = set()
    for raw in raw_files:
        entry = _safe_evidence_file_entry(raw)
        if not entry:
            continue
        key = entry["url"]
        if key in seen:
            continue
        seen.add(key)
        files.append(entry)
    return files


def get_submission_binder_evidence_manifest(
    pack_id: str,
    rfq_reference: str | None = None,
) -> Dict[str, Any]:
    gate = get_submission_binder_gate(pack_id, rfq_reference)
    checklist = get_submission_binder_gate_checklist(pack_id, rfq_reference, include_text=True)
    audit_log = get_submission_binder_gate_audit_log(pack_id, rfq_reference)
    matched_binder = gate.get("matched_binder") if isinstance(gate.get("matched_binder"), dict) else None
    generated_at = _safe_text(audit_log.get("generated_at"), 80) or _now_iso()
    return {
        "status": gate.get("status"),
        "pack_id": gate.get("pack_id"),
        "rfq_reference": gate.get("rfq_reference"),
        "generated_at": generated_at,
        "binder_score": gate.get("binder_score", 0),
        "readiness_status": audit_log.get("readiness_status") or _submission_gate_readiness_status(gate),
        "checklist_available": bool(checklist.get("checklist_text")),
        "audit_exports_available": {
            "json": True,
            "txt": True,
        },
        "matched_binder": matched_binder,
        "evidence_files": _submission_gate_evidence_files(matched_binder),
        "missing_returnables": gate.get("missing_returnables", []),
        "blockers": gate.get("blockers", []),
        "manual_completion_required": True,
        "manual_completion": gate.get("manual_completion"),
        "manual_completion_allowed": gate.get("manual_completion_allowed", False),
        "manual_completion_blocked_reason": gate.get("manual_completion_blocked_reason", ""),
        "safety_flags": gate.get("safety_flags", dict(BINDER_SAFETY_FLAGS)),
        "final_submit_locked": True,
    }


def get_submission_binder_pack_summary(
    pack_id: str,
    rfq_reference: str | None = None,
) -> Dict[str, Any]:
    gate = get_submission_binder_gate(pack_id, rfq_reference)
    checklist = get_submission_binder_gate_checklist(pack_id, rfq_reference, include_text=True)
    audit_log = get_submission_binder_gate_audit_log(pack_id, rfq_reference)
    evidence_manifest = get_submission_binder_evidence_manifest(pack_id, rfq_reference)
    operator_next_steps = [
        _safe_text(step, 320)
        for step in checklist.get("manual_upload_steps", [])
        if _safe_text(step, 320)
    ]
    if not operator_next_steps:
        operator_next_steps = _manual_upload_steps(gate)

    return {
        "status": gate.get("status"),
        "pack_id": gate.get("pack_id"),
        "rfq_reference": gate.get("rfq_reference"),
        "generated_at": _safe_text(evidence_manifest.get("generated_at"), 80) or _now_iso(),
        "gate_status": gate.get("status"),
        "checklist_available": bool(checklist.get("checklist_text")),
        "audit_log_available": bool(audit_log.get("events")),
        "evidence_manifest_available": bool(evidence_manifest.get("status")),
        "binder_score": gate.get("binder_score", 0),
        "readiness_status": audit_log.get("readiness_status") or evidence_manifest.get("readiness_status") or _submission_gate_readiness_status(gate),
        "missing_returnables": gate.get("missing_returnables", []),
        "blockers": gate.get("blockers", []),
        "manual_completion_required": True,
        "manual_completion": gate.get("manual_completion"),
        "manual_completion_allowed": gate.get("manual_completion_allowed", False),
        "manual_completion_blocked_reason": gate.get("manual_completion_blocked_reason", ""),
        "safety_flags": gate.get("safety_flags", dict(BINDER_SAFETY_FLAGS)),
        "evidence_files_count": len(evidence_manifest.get("evidence_files") or []),
        "final_submit_locked": True,
        "operator_next_steps": operator_next_steps,
        "message": "Submission pack summary is read-only. Final submission is blocked by design. Manual upload only.",
    }


def _write_submission_binder_files(workspace: Path) -> Dict[str, Any]:
    created_at = _now_iso()
    readiness = _submission_binder_readiness(workspace)
    source_files = _submission_binder_source_files(workspace)

    readiness_payload = {
        "pack_id": workspace.name,
        "created_at": created_at,
        "readiness": readiness,
        "safety": dict(BINDER_SAFETY_FLAGS),
    }
    readiness_path = workspace / "submission_binder_readiness.json"
    _write_json(readiness_path, readiness_payload)

    index_path = workspace / "submission_binder_index.txt"
    index_lines = [
        "SUBMISSION BINDER INDEX",
        "LOCAL SUBMISSION BINDER ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED - FINAL SUBMIT LOCKED",
        "",
        f"Pack ID: {workspace.name}",
        f"Generated at: {created_at}",
        f"Readiness score: {readiness['submission_binder_score']}%",
        "",
        "Source files:",
    ]
    index_lines.extend(f"- {file.get('name')} ({file.get('type')}) {file.get('path')}" for file in source_files)
    index_lines.extend(["", "Missing items:", *[f"- {item}" for item in readiness["missing_items"]]])
    index_path.write_text("\n".join(index_lines), encoding="utf-8")

    review_path = workspace / "operator_submission_binder_review.txt"
    review_lines = [
        "OPERATOR SUBMISSION BINDER REVIEW",
        "LOCAL SUBMISSION BINDER ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED - FINAL SUBMIT LOCKED",
        "",
        "Operator checks:",
        "- Confirm all binder source files are correct and current.",
        "- Confirm pricing, formal quote, and returnables review are complete.",
        "- Do not submit, email, upload, or bypass portal controls from this system.",
        "",
        "Blockers:",
    ]
    review_lines.extend(f"- {blocker}" for blocker in readiness["blockers"])
    if not readiness["blockers"]:
        review_lines.append("- No binder blockers detected.")
    review_path.write_text("\n".join(review_lines), encoding="utf-8")

    manifest = _submission_binder_manifest(workspace, created_at=created_at)
    manifest_path = workspace / "submission_binder_manifest.json"
    _write_json(manifest_path, manifest)
    manifest["binder_files"] = _submission_binder_files(workspace)
    manifest["source_files"] = _submission_binder_source_files(workspace)
    _write_json(manifest_path, manifest)
    return manifest


def _write_placeholder(workspace: Path, filename: str, label: str, candidate: Dict[str, Any]) -> Path:
    path = workspace / filename
    path.write_text(
        "\n".join(
            [
                f"{label}",
                "",
                "LOCAL PLACEHOLDER ONLY",
                "This file was generated because the source artifact was not detected.",
                "It is for operator review and must not be submitted without replacement.",
                f"RFQ Reference: {candidate.get('rfq_reference')}",
                f"Generated at: {_now_iso()}",
            ]
        ),
        encoding="utf-8",
    )
    return path


class QuoteCompilationService:
    """Local-only quote pack compilation helper."""

    def status(self) -> Dict[str, Any]:
        candidate_data = _load_candidates(limit=DEFAULT_LIMIT)
        latest_pack = None
        if OUTPUT_ROOT.exists():
            pack_dirs = sorted(
                [path for path in OUTPUT_ROOT.iterdir() if path.is_dir()],
                key=lambda path: _modified_at(path),
                reverse=True,
            )
            if pack_dirs:
                latest_pack = _relative(pack_dirs[0])
        return {
            "status": "ok",
            "service": "quote_compilation",
            "service_version": SERVICE_VERSION,
            "read_only": True,
            "output_root": _relative(OUTPUT_ROOT),
            "candidate_count": candidate_data["total_candidates"],
            "latest_pack": latest_pack,
            "safety": dict(SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def candidates(self, limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
        result = _load_candidates(limit=limit)
        result["status"] = "ok"
        return result

    def packs(self, limit: int = MAX_PACKS_RETURNED) -> Dict[str, Any]:
        pack_dirs = _quote_pack_dirs()
        safe_limit = max(1, min(int(limit or MAX_PACKS_RETURNED), MAX_PACKS_RETURNED))
        items = [_pack_detail(workspace) for workspace in pack_dirs[:safe_limit]]
        return {
            "status": "ok",
            "service": "quote_compilation",
            "read_only": True,
            "output_root": _relative(OUTPUT_ROOT),
            "items": items,
            "count": len(items),
            "total_packs": len(pack_dirs),
            "safety": dict(SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def latest_pack(self) -> Dict[str, Any]:
        pack_dirs = _quote_pack_dirs()
        if not pack_dirs:
            return {
                "status": "not_found",
                "message": "No local quote compilation packs were found.",
                "read_only": True,
                "output_root": _relative(OUTPUT_ROOT),
                "safety": dict(SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        return {
            "status": "ok",
            **_pack_detail(pack_dirs[0]),
            "timestamp": _now_iso(),
        }

    def submission_binders(self, limit: int = MAX_PACKS_RETURNED) -> Dict[str, Any]:
        pack_dirs = _quote_pack_dirs()
        safe_limit = max(1, min(int(limit or MAX_PACKS_RETURNED), MAX_PACKS_RETURNED))
        items: List[Dict[str, Any]] = []
        for workspace in pack_dirs[:safe_limit]:
            item = _submission_binder_list_item(workspace)
            if item:
                items.append(item)

        return {
            "status": "ok",
            "service": "quote_compilation",
            "read_only": True,
            "output_root": _relative(OUTPUT_ROOT),
            "items": items,
            "count": len(items),
            "total_packs": len(pack_dirs),
            "safety": dict(BINDER_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def submission_gate(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        gate = get_submission_binder_gate(pack_id, rfq_reference)
        if gate.get("pack_id"):
            append_pack_audit_event(
                gate.get("pack_id") or pack_id,
                "submission_gate_readiness_check",
                {
                    "allowed": bool(gate.get("can_submit_final")),
                    "can_prepare_submission": bool(gate.get("can_prepare_submission")),
                    "manual_completion_allowed": bool(gate.get("manual_completion_allowed")),
                    "manual_completion_blocked_reason": gate.get("manual_completion_blocked_reason"),
                    "readiness_status": gate.get("readiness_status"),
                    "reason_code": gate.get("manual_completion", {}).get("reason_code") if isinstance(gate.get("manual_completion"), dict) else None,
                },
            )
            manual_completion = gate.get("manual_completion") if isinstance(gate.get("manual_completion"), dict) else {}
            if manual_completion and manual_completion.get("allowed") is False:
                append_pack_audit_event(
                    gate.get("pack_id") or pack_id,
                    "submission_gate_blocked_invalid_manual_completion" if manual_completion.get("reason_code") == "manual_completion_invalid_json" or str(manual_completion.get("reason_code") or "").startswith("manual_completion_invalid") or manual_completion.get("reason_code") == "manual_completion_credential_like_content" else "submission_gate_blocked_missing_manual_completion",
                    {
                        "blocked_reason": manual_completion.get("blocked_reason"),
                        "reason_code": manual_completion.get("reason_code"),
                        "missing_fields": manual_completion.get("missing_fields", []),
                        "forbidden_fields": manual_completion.get("forbidden_fields", []),
                        "manual_completion_path": manual_completion.get("manual_completion_path"),
                    },
                )
        return {
            **gate,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def submission_gate_checklist(
        self,
        pack_id: str,
        rfq_reference: Optional[str] = None,
        include_text: bool = True,
    ) -> Dict[str, Any]:
        checklist = get_submission_binder_gate_checklist(pack_id, rfq_reference, include_text=include_text)
        return {
            **checklist,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def submission_gate_audit_log(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        audit_log = get_submission_binder_gate_audit_log(pack_id, rfq_reference)
        return {
            **audit_log,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def submission_gate_audit_log_text(self, pack_id: str, rfq_reference: Optional[str] = None) -> str:
        return _submission_gate_audit_log_text(self.submission_gate_audit_log(pack_id, rfq_reference))

    def submission_gate_evidence_manifest(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        manifest = get_submission_binder_evidence_manifest(pack_id, rfq_reference)
        return {
            **manifest,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def submission_gate_summary(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        summary = get_submission_binder_pack_summary(pack_id, rfq_reference)
        return {
            **summary,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def compliance_summary(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        summary = get_submission_binder_compliance_summary(pack_id, rfq_reference)
        return {
            **summary,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def readiness_checklist(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        checklist = get_submission_binder_readiness_checklist(pack_id, rfq_reference)
        return {
            **checklist,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def evidence_bundle(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        bundle = get_submission_binder_evidence_bundle(pack_id, rfq_reference)
        return {
            **bundle,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def evidence_snapshot(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        snapshot = get_submission_binder_evidence_snapshot(pack_id, rfq_reference)
        return {
            **snapshot,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def create_compliance_archive(
        self,
        pack_id: str,
        rfq_reference: Optional[str] = None,
        operator_role: Optional[str] = None,
        operator_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        operator = require_operator_access("compliance_archive_create", operator_role, operator_name)
        archive = create_compliance_archive(pack_id, rfq_reference=rfq_reference, operator=operator)
        return {
            **archive,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def read_compliance_archives(self, pack_id: str) -> Dict[str, Any]:
        archives = read_compliance_archives(pack_id)
        return {
            **archives,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def build_compliance_bundle_zip(
        self,
        pack_id: str,
        archive_id: Optional[str] = None,
        operator_role: Optional[str] = None,
        operator_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        operator = require_operator_access("compliance_archive_zip_export", operator_role, operator_name)
        bundle = build_compliance_bundle_zip(pack_id, archive_id=archive_id, operator=operator)
        return {
            **bundle,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def printable_report(self, pack_id: str, rfq_reference: Optional[str] = None) -> Dict[str, Any]:
        report = build_printable_compliance_report(pack_id, rfq_reference)
        return {
            **report,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def validate_submission_proof(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return validate_submission_proof(payload)

    def load_submission_proof(
        self,
        pack_id: str,
        operator_role: Optional[str] = None,
        operator_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        operator = require_operator_access("submission_proof_load", operator_role, operator_name)
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "read_only": True,
                "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        validation = _submission_proof_gate(workspace)
        append_pack_audit_event(
            workspace.name,
            "submission_proof_viewed",
            _with_operator_audit_payload({
                "allowed": bool(validation.get("allowed")),
                "reason_code": validation.get("reason_code"),
                "blocked_reason": validation.get("blocked_reason"),
                "saved_at": validation.get("submission_proof", {}).get("saved_at") if isinstance(validation.get("submission_proof"), dict) else None,
            }, operator),
        )
        return {
            **_submission_proof_detail(workspace),
            "validation": validation,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def export_submission_proof(
        self,
        pack_id: str,
        operator_role: Optional[str] = None,
        operator_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        operator = require_operator_access("submission_proof_export", operator_role, operator_name)
        proof = self.load_submission_proof(pack_id, operator_role=operator.role, operator_name=operator.name)
        if proof.get("status") in {"ok", "invalid"}:
            append_pack_audit_event(
                proof.get("pack_id") or _safe_text(pack_id, 160),
                "submission_proof_exported",
                _with_operator_audit_payload({
                    "status": proof.get("status"),
                    "validation_status": proof.get("validation", {}).get("status") if isinstance(proof.get("validation"), dict) else None,
                    "submission_proof_allowed": bool(proof.get("validation", {}).get("allowed")) if isinstance(proof.get("validation"), dict) else None,
                }, operator),
            )
        return proof

    def manual_completion(self, pack_id: str) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "read_only": True,
                "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        validation = _manual_completion_gate(workspace)
        append_pack_audit_event(
            workspace.name,
            "manual_completion_get",
            {
                "allowed": bool(validation.get("allowed")),
                "reason_code": validation.get("reason_code"),
                "blocked_reason": validation.get("blocked_reason"),
                "saved_at": validation.get("manual_completion", {}).get("saved_at") if isinstance(validation.get("manual_completion"), dict) else None,
            },
        )
        return {
            **_manual_completion_detail(workspace),
            "validation": validation,
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def save_submission_proof(
        self,
        pack_id: str,
        payload: Optional[Dict[str, Any]] = None,
        operator_role: Optional[str] = None,
        operator_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        operator = require_operator_access("submission_proof_save", operator_role, operator_name)
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }

        try:
            submission_proof = validate_submission_proof(payload or {})
        except ValueError as exc:
            append_pack_audit_event(
                pack_id,
                "submission_proof_validation_failure",
                _with_operator_audit_payload({
                    "error": str(exc),
                    "field_names": list((payload or {}).keys()) if isinstance(payload, dict) else [],
                }, operator),
            )
            raise

        submission_proof["pack_id"] = workspace.name
        submission_proof_path = _submission_proof_path(workspace)
        _write_json(submission_proof_path, submission_proof)
        append_pack_audit_event(
            workspace.name,
            "submission_proof_save_success",
            _with_operator_audit_payload({
                "submitted_by": submission_proof.get("submitted_by"),
                "submission_timestamp": submission_proof.get("submission_timestamp"),
                "portal_name": submission_proof.get("portal_name"),
                "portal_reference": submission_proof.get("portal_reference"),
                "uploaded_file_count": len(submission_proof.get("uploaded_files") or []),
                "saved_at": submission_proof.get("saved_at"),
            }, operator),
        )

        return {
            "status": "ok",
            "message": "Submission proof record saved locally. No portal action was performed.",
            "submission_proof": submission_proof,
            "files": [
                _pack_file_entry(submission_proof_path, "submission_proof"),
            ],
            "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
            "read_only": True,
            "timestamp": _now_iso(),
        }

    def save_manual_completion(self, pack_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }

        try:
            manual_completion = _normalize_manual_completion_payload(workspace, payload or {})
        except ValueError as exc:
            append_pack_audit_event(
                pack_id,
                "manual_completion_validation_failure",
                {
                    "error": str(exc),
                    "field_names": list((payload or {}).keys()) if isinstance(payload, dict) else [],
                },
            )
            raise
        manual_completion_path = _manual_completion_path(workspace)
        _write_json(manual_completion_path, manual_completion)
        append_pack_audit_event(
            workspace.name,
            "manual_completion_save_success",
            {
                "submitted_by": manual_completion.get("submitted_by"),
                "submitted_at": manual_completion.get("submitted_at"),
                "portal_name": manual_completion.get("portal_name"),
                "portal_reference": manual_completion.get("portal_reference"),
                "uploaded_file_count": len(manual_completion.get("uploaded_file_names") or []),
                "notes_present": bool(manual_completion.get("notes")),
                "saved_at": manual_completion.get("saved_at"),
            },
        )

        return {
            "status": "ok",
            "message": "Manual completion record saved locally. No submission, upload, email, or portal action was performed.",
            "manual_completion": manual_completion,
            "files": [
                _pack_file_entry(manual_completion_path, "manual_completion"),
            ],
            "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def audit_trail(self, pack_id: str) -> Dict[str, Any]:
        workspace = _pack_audit_workspace(pack_id, create=False)
        if not workspace:
            return {
                "status": "ok",
                "pack_id": _safe_text(pack_id, 160),
                "audit_trail_path": _relative(_audit_trail_path(OUTPUT_ROOT / _safe_text(pack_id, 160))),
                "events": [],
                "warning_count": 0,
                "count": 0,
                "read_only": True,
                "safety": dict(MANUAL_COMPLETION_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        return _read_pack_audit_trail(workspace)

    def pack(self, pack_id: str) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "read_only": True,
                "safety": dict(SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        return {
            "status": "ok",
            **_pack_detail(workspace),
            "timestamp": _now_iso(),
        }

    def pack_pricing(self, pack_id: str) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "read_only": True,
                "safety": dict(PRICING_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        return {
            "status": "ok",
            "read_only": True,
            "pricing": _calculate_pricing_model(workspace),
            "timestamp": _now_iso(),
        }

    def pricing_dry_run(self, pack_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "dry_run": True,
                "safety": dict(PRICING_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        return {
            "status": "ok",
            "dry_run": True,
            "would_write": [
                _relative(workspace / "pricing_schedule_completed.json"),
                _relative(workspace / "pricing_schedule_completed.csv"),
            ],
            "pricing": _calculate_pricing_model(workspace, payload or {}, source="dry_run"),
            "safety": dict(PRICING_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def save_local_pricing(self, pack_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "safety": dict(PRICING_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }

        pricing = _calculate_pricing_model(workspace, payload or {}, source="saved_local")
        pricing["saved_at"] = _now_iso()
        json_path = workspace / "pricing_schedule_completed.json"
        csv_path = workspace / "pricing_schedule_completed.csv"
        _write_json(json_path, pricing)
        _write_pricing_csv(csv_path, pricing)

        return {
            "status": "ok",
            "message": "Local pricing schedule saved. No submission, upload, or email action was performed.",
            "pricing": pricing,
            "files": [
                _pack_file_entry(json_path, "pricing_schedule_completed"),
                _pack_file_entry(csv_path, "pricing_schedule_completed_csv"),
            ],
            "safety": dict(PRICING_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def formal_quote(self, pack_id: str) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "read_only": True,
                "safety": dict(PRICING_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        return _formal_quote_detail(workspace)

    def generate_local_formal_quote(self, pack_id: str) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "safety": dict(PRICING_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }

        pricing = _safe_read_pack_json(workspace, "pricing_schedule_completed.json")
        if not isinstance(pricing, dict):
            return {
                "status": "pricing_required",
                "message": "Pricing schedule must be saved locally before formal quote generation.",
                "pack_id": workspace.name,
                "safety": dict(PRICING_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }

        summary = _write_formal_quote_files(workspace, pricing)
        return {
            "status": "ok",
            "message": "Local formal quote generated. No submission, upload, or email action was performed.",
            "pack_id": workspace.name,
            "formal_quote_summary": summary,
            "generated_files": summary.get("generated_files", []),
            "safety": dict(PRICING_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def returnables(self, pack_id: str) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "read_only": True,
                "safety": dict(PRICING_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        return {
            "status": "ok",
            "read_only": True,
            "returnables_review": _normalize_returnables_model(workspace),
            "files": [
                _pack_file_entry(path, file_type)
                for path, file_type in (
                    (workspace / "returnables_completion.json", "returnables_completion"),
                    (workspace / "returnables_completion_summary.txt", "returnables_completion_summary"),
                )
                if path.exists() and path.is_file()
            ],
            "safety": dict(PRICING_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def save_local_returnables(self, pack_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "safety": dict(PRICING_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }

        model = _normalize_returnables_model(workspace, payload or {})
        model["updated_at"] = _now_iso()
        json_path = workspace / "returnables_completion.json"
        summary_path = workspace / "returnables_completion_summary.txt"
        _write_json(json_path, model)
        _write_returnables_summary(summary_path, model)

        return {
            "status": "ok",
            "message": "Local returnables review saved. No submission, upload, or email action was performed.",
            "returnables_review": model,
            "files": [
                _pack_file_entry(json_path, "returnables_completion"),
                _pack_file_entry(summary_path, "returnables_completion_summary"),
            ],
            "safety": dict(PRICING_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def submission_binder(self, pack_id: str) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "read_only": True,
                "safety": dict(BINDER_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        return _submission_binder_detail(workspace)

    def generate_local_submission_binder(self, pack_id: str) -> Dict[str, Any]:
        workspace = _safe_quote_pack_dir(pack_id)
        if not workspace:
            return {
                "status": "not_found",
                "message": "No local quote compilation pack matched the requested pack_id.",
                "pack_id": _safe_text(pack_id, 160),
                "safety": dict(BINDER_SAFETY_FLAGS),
                "timestamp": _now_iso(),
            }
        manifest = _write_submission_binder_files(workspace)
        return {
            "status": "ok",
            "message": "Local submission binder generated. No submission, upload, email, or final submit action was performed.",
            "pack_id": workspace.name,
            "submission_binder_manifest": manifest,
            "readiness": manifest.get("readiness", {}),
            "binder_files": manifest.get("binder_files", []),
            "source_files": manifest.get("source_files", []),
            "safety": dict(BINDER_SAFETY_FLAGS),
            "timestamp": _now_iso(),
        }

    def dry_run(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        candidate = _select_candidate(payload)
        if not candidate:
            return {
                "status": "not_found",
                "message": "No quote compilation candidate matched the request.",
                "dry_run": True,
                "safety": dict(SAFETY_FLAGS),
            }
        missing = candidate.get("readiness", {}).get("missing_items", [])
        would_create = [
            "quote_summary.json",
            "quote_pack_manifest.json",
            "pricing_schedule_review.json",
            "returnables_checklist.json",
            "operator_next_steps.txt",
        ]
        for item in missing:
            would_create.append(f"placeholder_{item}.txt")
        return {
            "status": "ok",
            "dry_run": True,
            "candidate": candidate,
            "manifest_preview": _manifest_preview(candidate),
            "would_create_files": would_create,
            "safety": dict(SAFETY_FLAGS),
        }

    def generate_local_pack(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        candidate = _select_candidate(payload)
        if not candidate:
            return {
                "status": "not_found",
                "message": "No quote compilation candidate matched the request.",
                "safety": dict(SAFETY_FLAGS),
            }

        pack_id = f"QCP-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{_safe_name(candidate.get('rfq_reference'), 'RFQ')[:60]}"
        workspace = _safe_workspace(pack_id)
        files: List[Dict[str, Any]] = []

        quote_summary = {
            "pack_id": pack_id,
            "rfq_reference": candidate.get("rfq_reference"),
            "title": candidate.get("title"),
            "buyer": candidate.get("buyer"),
            "estimated_value": candidate.get("estimated_value"),
            "estimated_profit": candidate.get("estimated_profit"),
            "margin_percent": candidate.get("margin_percent"),
            "recommended_next_step": candidate.get("recommended_next_step"),
            "safety": dict(SAFETY_FLAGS),
        }
        quote_summary_path = workspace / "quote_summary.json"
        _write_json(quote_summary_path, quote_summary)
        files.append(_file_entry(quote_summary_path, "quote_summary"))

        pricing_review = {
            "rfq_reference": candidate.get("rfq_reference"),
            "pricing_schedule_found": candidate.get("readiness", {}).get("pricing_schedule_found"),
            "boq_found": candidate.get("readiness", {}).get("boq_found"),
            "pricing_schedules": candidate.get("artifacts", {}).get("pricing_schedules", []),
            "boqs": candidate.get("artifacts", {}).get("boqs", []),
            "safety": dict(SAFETY_FLAGS),
        }
        pricing_review_path = workspace / "pricing_schedule_review.json"
        _write_json(pricing_review_path, pricing_review)
        files.append(_file_entry(pricing_review_path, "pricing_schedule_review"))

        checklist = {
            "rfq_reference": candidate.get("rfq_reference"),
            "buyer_forms_found": candidate.get("readiness", {}).get("buyer_forms_found"),
            "sbd_forms_found": candidate.get("readiness", {}).get("sbd_forms_found"),
            "buyer_docs": candidate.get("artifacts", {}).get("buyer_docs", []),
            "sbd_forms": candidate.get("artifacts", {}).get("sbd_forms", []),
            "missing_items": candidate.get("readiness", {}).get("missing_items", []),
            "safety": dict(SAFETY_FLAGS),
        }
        checklist_path = workspace / "returnables_checklist.json"
        _write_json(checklist_path, checklist)
        files.append(_file_entry(checklist_path, "returnables_checklist"))

        next_steps_path = workspace / "operator_next_steps.txt"
        next_steps_path.write_text(
            "\n".join(
                [
                    "LOCAL ONLY - NOT SUBMITTED - NOT EMAILED - NOT UPLOADED",
                    "",
                    f"RFQ Reference: {candidate.get('rfq_reference')}",
                    f"Recommended next step: {candidate.get('recommended_next_step')}",
                    "",
                    "Operator checks:",
                    "- Review generated JSON files.",
                    "- Replace any placeholder file with real buyer material before submission review.",
                    "- Confirm pricing, BOQ, buyer forms, and SBD returnables manually.",
                ]
            ),
            encoding="utf-8",
        )
        files.append(_file_entry(next_steps_path, "operator_next_steps"))

        missing_items = candidate.get("readiness", {}).get("missing_items", [])
        placeholder_labels = {
            "pricing_schedule": "Pricing Schedule Placeholder",
            "boq": "BOQ Placeholder",
            "buyer_forms": "Buyer Forms Placeholder",
            "sbd_forms": "SBD Forms Placeholder",
        }
        for missing_item in missing_items:
            filename = f"placeholder_{_safe_name(missing_item, 'missing')}.txt"
            placeholder_path = _write_placeholder(
                workspace,
                filename,
                placeholder_labels.get(missing_item, f"{missing_item} Placeholder"),
                candidate,
            )
            files.append(_file_entry(placeholder_path, "placeholder"))

        manifest = _manifest_preview(candidate, pack_id=pack_id)
        manifest["files"] = files + [
            {
                "name": "quote_pack_manifest.json",
                "path": _relative(workspace / "quote_pack_manifest.json"),
                "type": "quote_pack_manifest",
                "size_bytes": 0,
            }
        ]
        manifest_path = workspace / "quote_pack_manifest.json"
        _write_json(manifest_path, manifest)
        manifest["files"][-1] = _file_entry(manifest_path, "quote_pack_manifest")

        # Rewrite once with the final manifest file size included.
        _write_json(manifest_path, manifest)

        return {
            "status": "ok",
            "message": "Local quote pack generated. No submission, upload, email, or CAPTCHA action was performed.",
            "workspace": _relative(workspace),
            "manifest_path": _relative(manifest_path),
            "manifest": manifest,
            "candidate": candidate,
            "safety": dict(SAFETY_FLAGS),
        }
