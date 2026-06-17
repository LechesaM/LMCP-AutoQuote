from __future__ import annotations

import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


RUNTIME_DIR = Path("runtime")
PROOF_CENTER_DIR = RUNTIME_DIR / "proof_center"
PROOF_CENTER_DIR.mkdir(parents=True, exist_ok=True)

FINAL_PROOF_DIR = RUNTIME_DIR / "final_submission_v47_5" / "proofs"
PORTAL_PROOF_DIR = RUNTIME_DIR / "portal_submission" / "proofs"
SUBMISSION_PROOF_DIR = RUNTIME_DIR / "submission_proofs"

INDEX_FILE = PROOF_CENTER_DIR / "proof_index.json"
LAST_SCAN_FILE = PROOF_CENTER_DIR / "last_scan.json"


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _slug(value: Any, fallback: str = "proof") -> str:
    text = _safe_str(value, fallback)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return text[:140] or fallback


def _read_json(path: Optional[Path], default: Any) -> Any:
    try:
        if not path or not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _resolve_path(path_value: Any, runtime_dir: Optional[str] = None) -> Optional[Path]:
    text = _safe_str(path_value)
    if not text:
        return None

    candidates = [
        Path(text),
        Path("/app") / text,
        Path.cwd() / text,
        Path("/Users/Shared/LMCP-AutoQuote-Server") / text,
    ]
    if runtime_dir:
        candidates.insert(1, Path(runtime_dir).expanduser().resolve() / text)

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        except Exception:
            continue

    return None


def _file_info(path: Optional[Path]) -> Dict[str, Any]:
    if not path:
        return {"exists": False, "path": ""}

    try:
        stat = path.stat()
        return {
            "exists": True,
            "path": str(path),
            "name": path.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "mime_type": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
        }
    except Exception as exc:
        return {"exists": False, "path": str(path), "error": str(exc)}


def _get_nested(record: Dict[str, Any], key: str) -> Any:
    if key in record:
        return record.get(key)
    final_result = record.get("final_submission_result")
    if isinstance(final_result, dict) and key in final_result:
        return final_result.get(key)
    return None


def _extract_screenshot_paths(record: Dict[str, Any]) -> List[str]:
    keys = [
        "opened_screenshot",
        "after_start_screenshot",
        "after_upload_screenshot",
        "after_submit_screenshot",
        "proof_screenshot",
        "captcha_screenshot",
        "screenshot_path",
    ]

    paths: List[str] = []
    for key in keys:
        value = _get_nested(record, key)
        if value:
            paths.append(_safe_str(value))
    screenshot_paths = _get_nested(record, "screenshot_paths")
    if isinstance(screenshot_paths, list):
        paths.extend(_safe_str(item) for item in screenshot_paths if _safe_str(item))

    seen = set()
    output = []
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            output.append(p)
    return output


def _record_from_json(path: Path) -> Dict[str, Any]:
    data = _read_json(path, {})
    if not isinstance(data, dict):
        data = {}

    buyer_rfq = _get_nested(data, "buyer_rfq_number")
    quote_number = _get_nested(data, "quote_number")

    submitted = bool(
        data.get("submitted") is True
        or data.get("portal_auto_submitted") is True
        or _get_nested(data, "submitted") is True
        or _get_nested(data, "portal_auto_submitted") is True
    )

    status = _safe_str(_get_nested(data, "submission_status") or _get_nested(data, "status"))
    proof_info = _file_info(path)

    screenshots = []
    for screenshot in _extract_screenshot_paths(data):
        resolved = _resolve_path(screenshot, runtime_dir=None)
        screenshots.append(
            {
                "path": screenshot,
                "resolved_path": str(resolved) if resolved else "",
                "exists": bool(resolved),
                "name": Path(screenshot).name,
            }
        )

    record_id_seed = f"{buyer_rfq or ''}__{quote_number or ''}__{path.name}"
    record_id = _slug(record_id_seed)

    return {
        "record_id": record_id,
        "buyer_rfq_number": _safe_str(buyer_rfq, "UNKNOWN-RFQ"),
        "quote_number": _safe_str(quote_number, "UNKNOWN-QUOTE"),
        "submitted": submitted,
        "submission_status": status or ("submitted" if submitted else "unknown"),
        "portal_url": _safe_str(_get_nested(data, "portal_url")),
        "portal_domain": _safe_str(_get_nested(data, "portal_domain")),
        "proof_file": str(path),
        "proof_file_info": proof_info,
        "screenshots": screenshots,
        "screenshot_count": len([s for s in screenshots if s.get("exists")]),
        "submitted_at": _safe_str(_get_nested(data, "submitted_at")),
        "created_at": proof_info.get("modified_at", ""),
        "verification_level": _safe_str(_get_nested(data, "verification_level")),
        "verification_note": _safe_str(_get_nested(data, "verification_note")),
        "source": str(path.parent),
    }


def _scan_json_files() -> List[Path]:
    roots = [FINAL_PROOF_DIR, PORTAL_PROOF_DIR, SUBMISSION_PROOF_DIR]
    files: List[Path] = []

    for root in roots:
        try:
            if root.exists():
                files.extend([p for p in root.rglob("*.json") if p.is_file()])
        except Exception:
            continue

    unique = {}
    for p in files:
        try:
            unique[str(p.resolve())] = p.resolve()
        except Exception:
            unique[str(p)] = p

    return list(unique.values())


def scan_proof_center(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    index_file = _resolve_runtime_path(INDEX_FILE, runtime_dir)
    last_scan_file = _resolve_runtime_path(LAST_SCAN_FILE, runtime_dir)
    records = []

    for path in _scan_json_files():
        try:
            records.append(_record_from_json(path))
        except Exception as exc:
            records.append(
                {
                    "record_id": _slug(path.name),
                    "buyer_rfq_number": "UNKNOWN-RFQ",
                    "quote_number": "UNKNOWN-QUOTE",
                    "submitted": False,
                    "submission_status": "scan_error",
                    "proof_file": str(path),
                    "error": str(exc),
                }
            )

    records = sorted(records, key=lambda r: _safe_str(r.get("created_at") or r.get("submitted_at")), reverse=True)

    submitted_total = len([r for r in records if r.get("submitted") is True])
    pending_total = len(records) - submitted_total

    payload = {
        "status": "ok",
        "service_version": "PRODUCTION_PROOF_CENTER_V1",
        "summary": {
            "proof_total": len(records),
            "submitted_total": submitted_total,
            "pending_or_unverified_total": pending_total,
            "screenshot_total": sum(int(r.get("screenshot_count") or 0) for r in records),
        },
        "records": records,
        "scanned_at": _now(),
        "scan_roots": {
            "final_proofs": str(_resolve_runtime_path(FINAL_PROOF_DIR, runtime_dir)),
            "portal_proofs": str(_resolve_runtime_path(PORTAL_PROOF_DIR, runtime_dir)),
            "submission_proofs": str(_resolve_runtime_path(SUBMISSION_PROOF_DIR, runtime_dir)),
        },
        "files": {"index": str(index_file), "last_scan": str(last_scan_file)},
    }

    _write_json(index_file, payload)
    _write_json(last_scan_file, {"status": "ok", "scanned_at": payload["scanned_at"], "summary": payload["summary"]})
    return payload


def get_proof_center(limit: int = 100, submitted_only: bool = False, q: str = "", runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    index_file = _resolve_runtime_path(INDEX_FILE, runtime_dir)
    last_scan_file = _resolve_runtime_path(LAST_SCAN_FILE, runtime_dir)
    index = _read_json(index_file, None)
    if not isinstance(index, dict):
        index = scan_proof_center(runtime_dir=runtime_dir)

    records = index.get("records", [])
    if not isinstance(records, list):
        records = []

    if submitted_only:
        records = [r for r in records if r.get("submitted") is True]

    query = _safe_lower(q)
    if query:
        records = [
            r for r in records
            if query in _safe_lower(r.get("buyer_rfq_number"))
            or query in _safe_lower(r.get("quote_number"))
            or query in _safe_lower(r.get("portal_url"))
            or query in _safe_lower(r.get("submission_status"))
        ]

    limit = max(1, min(int(limit or 100), 500))
    return {
        "status": "ok",
        "service_version": "PRODUCTION_PROOF_CENTER_V1",
        "summary": {
            **(index.get("summary", {}) if isinstance(index.get("summary"), dict) else {}),
            "returned": min(len(records), limit),
            "filtered_total": len(records),
        },
        "records": records[:limit],
        "last_scan": _read_json(last_scan_file, {}),
        "updated_at": _now(),
    }


def get_proof_record(record_id: str, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    index = get_proof_center(limit=500, runtime_dir=runtime_dir)
    for record in index.get("records", []):
        if record.get("record_id") == record_id:
            proof_path = _resolve_path(record.get("proof_file"), runtime_dir=runtime_dir)
            raw = _read_json(proof_path, {}) if proof_path else {}
            return {"status": "ok", "record": record, "raw_proof": raw, "updated_at": _now()}

    return {"status": "not_found", "record_id": record_id, "message": "Proof record not found."}


def resolve_download_path(record_id: str, kind: str = "proof", screenshot_index: int = 0, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    found = get_proof_record(record_id, runtime_dir=runtime_dir)
    if found.get("status") != "ok":
        return found

    record = found["record"]

    if kind == "proof":
        path = _resolve_path(record.get("proof_file"), runtime_dir=runtime_dir)
    elif kind == "screenshot":
        screenshots = record.get("screenshots", [])
        if not isinstance(screenshots, list) or not screenshots:
            return {"status": "not_found", "message": "No screenshots available for this proof."}
        screenshot_index = max(0, int(screenshot_index or 0))
        if screenshot_index >= len(screenshots):
            return {"status": "not_found", "message": "Screenshot index out of range."}
        item = screenshots[screenshot_index]
        path = _resolve_path(item.get("path") or item.get("resolved_path"), runtime_dir=runtime_dir)
    else:
        return {"status": "error", "message": "kind must be 'proof' or 'screenshot'."}

    if not path:
        return {"status": "not_found", "message": "Download file not found on disk."}

    return {
        "status": "ok",
        "path": str(path),
        "filename": path.name,
        "media_type": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
    }
