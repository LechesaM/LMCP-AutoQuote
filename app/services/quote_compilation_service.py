from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SERVICE_VERSION = "QUOTE_COMPILATION_LOCAL_SAFE_V1"
BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = BASE_DIR / "runtime"
OUTPUT_ROOT = RUNTIME_DIR / "quote_compilation"
RFQ_STATE_FILE = RUNTIME_DIR / "rfq_lifecycle" / "rfqs.json"
MANUAL_COMPLETION_FILENAME = "manual_completion.json"

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

RETURNABLE_STATUSES = {"missing", "available", "completed", "not_applicable", "needs_review"}
SBD_FORM_NAMES = ("SBD 1", "SBD 4", "SBD 6.1", "SBD 8", "SBD 9")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, max_length: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def _strict_text(value: Any, max_length: int, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required.")
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds the maximum length of {max_length} characters.")
    return text


def _manual_completion_path(workspace: Path) -> Path:
    return workspace / MANUAL_COMPLETION_FILENAME


def _manual_completion_has_forbidden_fields(payload: Dict[str, Any]) -> bool:
    keys = " ".join(str(key).lower() for key in payload.keys())
    values = " ".join(_safe_text(value, 2000).lower() for value in payload.values())
    haystack = f"{keys} {values}"
    return any(re.search(rf"\b{re.escape(keyword)}\b", haystack) for keyword in FORBIDDEN_MANUAL_COMPLETION_KEYWORDS)


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
) -> str:
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

    if workspace:
        matched_binder = _submission_binder_list_item(workspace)

    if not matched_binder and requested_reference:
        reference_slug = _slug(requested_reference)
        for candidate in _quote_pack_dirs():
            item = _submission_binder_list_item(candidate)
            if item and reference_slug and _slug(item.get("rfq_reference")) == reference_slug:
                matched_binder = item
                workspace = candidate
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
        "can_submit_final": False,
        "binder_score": binder_score,
        "blockers": blockers,
        "missing_returnables": missing_returnables,
        "safety_flags": dict(BINDER_SAFETY_FLAGS),
        "matched_binder": matched_binder,
        "message": _submission_binder_gate_message(matched_binder, can_prepare_submission, blockers, missing_returnables),
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
    lines = [
        "MANUAL SUBMISSION CHECKLIST",
        "READ ONLY - LOCAL BINDER REVIEW - FINAL SUBMIT LOCKED",
        "",
        f"Pack ID: {checklist.get('pack_id') or ''}",
        f"RFQ Reference: {checklist.get('rfq_reference') or ''}",
        f"Binder Score: {checklist.get('binder_score')}",
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
        "manual_upload_steps": _manual_upload_steps(gate),
        "final_submit_warning": final_submit_warning,
        "can_submit_final": False,
        "message": gate.get("message") or final_submit_warning,
    }
    if include_text:
        checklist["checklist_text"] = _submission_gate_checklist_text(checklist)
    return checklist


def _submission_gate_readiness_status(gate: Dict[str, Any]) -> str:
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
        return {
            **_manual_completion_detail(workspace),
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

        manual_completion = _normalize_manual_completion_payload(workspace, payload or {})
        manual_completion_path = _manual_completion_path(workspace)
        _write_json(manual_completion_path, manual_completion)

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
