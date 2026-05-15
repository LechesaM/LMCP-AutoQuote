from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re
import shutil
import traceback

SERVICE_VERSION = "V47_PORTAL_SUBMISSION_ENGINE"
DEFAULT_OUTPUT_DIR = Path("runtime/portal_submission_v47")
DEFAULT_HISTORY_PATH = Path("runtime/submission_history/v47_portal_submission_history.json")

BLOCKED_PORTAL_UPLOAD_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".js", ".vbs"
}

ALLOWED_PORTAL_UPLOAD_EXTENSIONS = {
    ".pdf", ".csv", ".xlsx", ".xls", ".docx", ".doc", ".json", ".png", ".jpg", ".jpeg"
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: Any, fallback: str = "RFQ") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _resolve_path(value: str | Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _read_json(path_value: str | Path) -> Dict[str, Any]:
    path = _resolve_path(path_value)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_history(record: Dict[str, Any]) -> None:
    history_path = _resolve_path(DEFAULT_HISTORY_PATH)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    else:
        history = []

    history.append(record)
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_v45_manifest(workspace_path: str) -> Dict[str, Any]:
    workspace = _resolve_path(workspace_path)
    candidates = [
        workspace / "submission_manifest_v45.json",
        workspace / "submission_record_v46.json",
    ]

    for c in candidates:
        if c.exists():
            data = _read_json(c)
            data["_source_manifest_json"] = str(c)
            data["_source_workspace"] = str(workspace)
            return data

    matches = list(workspace.glob("*manifest*.json"))
    if matches:
        data = _read_json(matches[0])
        data["_source_manifest_json"] = str(matches[0])
        data["_source_workspace"] = str(workspace)
        return data

    raise FileNotFoundError(f"No V45 submission manifest found in {workspace}")


def _extract_attachments_from_manifest(manifest: Dict[str, Any]) -> List[str]:
    attachments: List[str] = []

    for row in manifest.get("attachments") or []:
        if isinstance(row, dict):
            path = row.get("path")
            if path:
                attachments.append(str(path))
        elif isinstance(row, str):
            attachments.append(row)

    email_draft = manifest.get("email_draft") or {}
    for path in email_draft.get("attachments") or []:
        attachments.append(str(path))

    # Some V46 records use attachments.included
    inc = ((manifest.get("attachments") or {}).get("included")) if isinstance(manifest.get("attachments"), dict) else None
    for row in inc or []:
        if isinstance(row, dict) and row.get("path"):
            attachments.append(str(row["path"]))

    # de-dupe
    out = []
    seen = set()
    for a in attachments:
        p = str(_resolve_path(a))
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _classify_portal_attachment(path_value: str) -> Dict[str, Any]:
    path = _resolve_path(path_value)
    suffix = path.suffix.lower()

    row = {
        "source": str(path),
        "filename": path.name,
        "extension": suffix,
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
        "allowed": False,
        "reason": "",
    }

    if not path.exists():
        row["reason"] = "file not found"
        return row

    if not path.is_file():
        row["reason"] = "not a file"
        return row

    if suffix in BLOCKED_PORTAL_UPLOAD_EXTENSIONS:
        row["reason"] = "blocked executable/script file type"
        return row

    if suffix not in ALLOWED_PORTAL_UPLOAD_EXTENSIONS:
        row["reason"] = "file type not in allowed portal upload list"
        return row

    row["allowed"] = True
    row["reason"] = "allowed"
    return row


def _copy_portal_files(attachments: List[Dict[str, Any]], upload_dir: Path) -> List[Dict[str, Any]]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    copied: List[Dict[str, Any]] = []

    for row in attachments:
        if not row.get("allowed"):
            copied.append({**row, "copied_to": None, "copy_status": "skipped"})
            continue

        src = _resolve_path(row["source"])
        dest = upload_dir / src.name

        try:
            shutil.copy2(src, dest)
            copied.append({**row, "copied_to": str(dest), "copy_status": "copied"})
        except Exception as exc:
            copied.append({**row, "copied_to": None, "copy_status": "copy_failed", "error": str(exc)})

    return copied


def _infer_portal_type(portal_url: Optional[str], buyer_name: Optional[str]) -> str:
    blob = f"{portal_url or ''} {buyer_name or ''}".lower()

    if "etenders" in blob or "ocds" in blob or "treasury" in blob:
        return "etenders"
    if "municipal" in blob or "municipality" in blob:
        return "municipal_portal"
    if "eskom" in blob or "transnet" in blob or "sanral" in blob:
        return "soe_portal"
    if portal_url:
        return "generic_portal"
    return "manual_portal"


def _build_portal_steps(portal_type: str) -> List[Dict[str, Any]]:
    common = [
        {"step": 1, "action": "Open portal and confirm correct RFQ/tender record.", "proof_required": True},
        {"step": 2, "action": "Confirm buyer RFQ number and closing date before upload.", "proof_required": True},
        {"step": 3, "action": "Upload quotation PDF and supporting compliance files individually. Do not upload ZIP unless portal explicitly requires it.", "proof_required": True},
        {"step": 4, "action": "Review all uploaded files and confirm no incorrect buyer/submission email is used.", "proof_required": True},
        {"step": 5, "action": "Submit only after final operator confirmation.", "proof_required": True},
        {"step": 6, "action": "Save portal receipt, confirmation number, screenshots, and timestamp.", "proof_required": True},
    ]

    if portal_type == "etenders":
        common.insert(1, {"step": 1.5, "action": "Use existing authenticated eTenders session where available; do not bypass CAPTCHA.", "proof_required": False})

    return common


def prepare_portal_submission_from_v45_workspace(
    workspace_path: str,
    buyer_rfq_number: Optional[str] = None,
    buyer_name: Optional[str] = None,
    portal_url: Optional[str] = None,
    output_dir: Optional[str] = None,
    require_operator_confirmation: bool = True,
) -> Dict[str, Any]:
    started_at = _now_iso()

    try:
        source_workspace = _resolve_path(workspace_path)
        if not source_workspace.exists():
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V45 workspace not found.",
                "workspace_path": str(source_workspace),
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        manifest = _load_v45_manifest(str(source_workspace))
        rfq = buyer_rfq_number or manifest.get("buyer_rfq_number") or "RFQ"
        quote_number = manifest.get("quote_number") or "LMCP-QUOTE"
        portal_type = _infer_portal_type(portal_url, buyer_name)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        if not out_root.is_absolute():
            out_root = Path.cwd() / out_root

        workspace = out_root / f"{_safe_name(rfq)}__PORTAL-{timestamp}"
        upload_dir = workspace / "portal_upload_files"
        proof_dir = workspace / "proof"
        proof_dir.mkdir(parents=True, exist_ok=True)

        raw_attachments = _extract_attachments_from_manifest(manifest)
        classified = [_classify_portal_attachment(p) for p in raw_attachments]
        copied = _copy_portal_files(classified, upload_dir)

        allowed_files = [x for x in copied if x.get("copy_status") == "copied"]
        skipped_files = [x for x in copied if x.get("copy_status") != "copied"]

        ready_for_portal = bool(allowed_files) and (
            not require_operator_confirmation
            or require_operator_confirmation
        )

        portal_manifest = {
            "status": "prepared",
            "service_version": SERVICE_VERSION,
            "message": "Portal submission pack prepared. Operator confirmation is required before final portal submission.",
            "buyer_rfq_number": rfq,
            "buyer_name": buyer_name,
            "quote_number": quote_number,
            "portal_url": portal_url,
            "portal_type": portal_type,
            "source_v45_workspace": str(source_workspace),
            "source_manifest_json": manifest.get("_source_manifest_json"),
            "workspace": str(workspace),
            "started_at": started_at,
            "completed_at": _now_iso(),
            "portal_submission_policy": {
                "auto_click_submit": False,
                "operator_confirmation_required": require_operator_confirmation,
                "zip_allowed": False,
                "captcha_bypass_allowed": False,
                "blocked_extensions": sorted(BLOCKED_PORTAL_UPLOAD_EXTENSIONS),
                "allowed_extensions": sorted(ALLOWED_PORTAL_UPLOAD_EXTENSIONS),
            },
            "upload_summary": {
                "ready_for_portal_upload": ready_for_portal,
                "upload_files_count": len(allowed_files),
                "skipped_files_count": len(skipped_files),
                "upload_dir": str(upload_dir),
                "proof_dir": str(proof_dir),
            },
            "upload_files": allowed_files,
            "skipped_files": skipped_files,
            "portal_steps": _build_portal_steps(portal_type),
            "proof_capture_template": {
                "portal_receipt_number": None,
                "submitted_at": None,
                "submitted_by": None,
                "proof_files": [],
                "notes": None,
            },
            "artifacts": {
                "portal_manifest_json": str(workspace / "portal_submission_manifest_v47.json"),
                "upload_dir": str(upload_dir),
                "proof_dir": str(proof_dir),
            },
        }

        _write_json(workspace / "portal_submission_manifest_v47.json", portal_manifest)
        _append_history(portal_manifest)

        return portal_manifest

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V47 portal submission preparation failed.",
            "workspace_path": workspace_path,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def prepare_portal_submission_from_pdf(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    buyer_name: Optional[str] = None,
    portal_url: Optional[str] = None,
    output_dir: Optional[str] = None,
    margin_percent: float = 25.0,
    minimum_profit_required: float = 30000.0,
    apply_profit_floor: bool = True,
    min_confidence: float = 0.35,
) -> Dict[str, Any]:
    started_at = _now_iso()

    try:
        from app.services.submission_pack_v45_service import prepare_submission_from_pdf

        v45_result = prepare_submission_from_pdf(
            input_pdf=input_pdf,
            buyer_rfq_number=buyer_rfq_number,
            margin_percent=margin_percent,
            minimum_profit_required=minimum_profit_required,
            apply_profit_floor=apply_profit_floor,
            min_confidence=min_confidence,
            create_zip=True,
        )

        if v45_result.get("status") != "ok":
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V45 failed, so V47 portal preparation could not continue.",
                "v45_result": v45_result,
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        result = prepare_portal_submission_from_v45_workspace(
            workspace_path=v45_result.get("workspace"),
            buyer_rfq_number=buyer_rfq_number,
            buyer_name=buyer_name,
            portal_url=portal_url,
            output_dir=output_dir,
            require_operator_confirmation=True,
        )
        result["v45_workspace"] = v45_result.get("workspace")
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V47 portal preparation from PDF failed.",
            "input_pdf": input_pdf,
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def record_portal_submission_proof(
    portal_manifest_json: str,
    portal_receipt_number: Optional[str] = None,
    submitted_by: Optional[str] = None,
    proof_files: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    started_at = _now_iso()

    try:
        manifest_path = _resolve_path(portal_manifest_json)
        if not manifest_path.exists():
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "Portal manifest JSON not found.",
                "portal_manifest_json": str(manifest_path),
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        manifest = _read_json(manifest_path)
        workspace = _resolve_path(manifest.get("workspace") or manifest_path.parent)
        proof_dir = workspace / "proof"
        proof_dir.mkdir(parents=True, exist_ok=True)

        copied_proofs: List[Dict[str, Any]] = []
        for proof in proof_files or []:
            src = _resolve_path(proof)
            if not src.exists() or not src.is_file():
                copied_proofs.append({"source": str(src), "status": "missing"})
                continue

            dest = proof_dir / src.name
            shutil.copy2(src, dest)
            copied_proofs.append({"source": str(src), "copied_to": str(dest), "status": "copied"})

        proof_record = {
            "status": "submitted_proof_recorded",
            "service_version": SERVICE_VERSION,
            "buyer_rfq_number": manifest.get("buyer_rfq_number"),
            "quote_number": manifest.get("quote_number"),
            "portal_url": manifest.get("portal_url"),
            "portal_type": manifest.get("portal_type"),
            "portal_receipt_number": portal_receipt_number,
            "submitted_by": submitted_by,
            "submitted_at": _now_iso(),
            "notes": notes,
            "proof_files": copied_proofs,
            "source_portal_manifest_json": str(manifest_path),
            "proof_record_json": str(workspace / "portal_submission_proof_v47.json"),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }

        _write_json(workspace / "portal_submission_proof_v47.json", proof_record)

        manifest["status"] = "submitted_proof_recorded"
        manifest["proof_capture_template"] = {
            "portal_receipt_number": portal_receipt_number,
            "submitted_at": proof_record["submitted_at"],
            "submitted_by": submitted_by,
            "proof_files": copied_proofs,
            "notes": notes,
        }
        _write_json(manifest_path, manifest)
        _append_history(proof_record)

        return proof_record

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Recording portal submission proof failed.",
            "portal_manifest_json": portal_manifest_json,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v47_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V47 Portal Submission Engine",
        "description": "Prepares portal-ready upload files from V45 packs, validates portal attachment rules, creates a manifest/checklist, and records submission proof. Does not bypass CAPTCHA or auto-click final submit without operator confirmation.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "history_path": str(DEFAULT_HISTORY_PATH),
        "portal_submission_policy": {
            "auto_click_submit": False,
            "operator_confirmation_required": True,
            "zip_allowed": False,
            "captcha_bypass_allowed": False,
            "blocked_extensions": sorted(BLOCKED_PORTAL_UPLOAD_EXTENSIONS),
            "allowed_extensions": sorted(ALLOWED_PORTAL_UPLOAD_EXTENSIONS),
        },
        "endpoints": {
            "status": "/v47-portal-submission/status",
            "prepare_from_v45_workspace": "/v47-portal-submission/prepare-from-v45-workspace",
            "prepare_from_pdf": "/v47-portal-submission/prepare-from-pdf",
            "record_proof": "/v47-portal-submission/record-proof",
        },
        "ready": True,
    }
