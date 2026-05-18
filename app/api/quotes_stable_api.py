from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter


router = APIRouter(prefix="/api/quotes", tags=["stable-quotes"])

BASE_DIR = Path(__file__).resolve().parents[2]
RECENT_LIMIT = 50
MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_SCAN_FILES_PER_DIR = 2500
MAX_SCAN_DEPTH = 5

SAFE_SOURCE_DIRS: Dict[str, Path] = {
    "monthly_quotes": BASE_DIR / "monthly_quotes",
    "runtime/rfq_lifecycle": BASE_DIR / "runtime" / "rfq_lifecycle",
    "runtime/submission_packs": BASE_DIR / "runtime" / "submission_packs",
    "runtime/quote_packs": BASE_DIR / "runtime" / "quote_packs",
    "runtime/submission_pack": BASE_DIR / "runtime" / "submission_pack",
    "runtime/final_submission_v47_5": BASE_DIR / "runtime" / "final_submission_v47_5",
}

SAFE_DOC_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".docx"}
SAFE_JSON_FILES = [
    SAFE_SOURCE_DIRS["runtime/rfq_lifecycle"] / "rfqs.json",
    SAFE_SOURCE_DIRS["runtime/final_submission_v47_5"] / "final_submission_history.json",
    SAFE_SOURCE_DIRS["runtime/final_submission_v47_5"] / "last_final_submit.json",
    SAFE_SOURCE_DIRS["runtime/final_submission_v47_5"] / "assisted_final_submit_required.json",
]

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

READY_QUOTE_STATES = {
    "generated",
    "ready",
    "quote_pack_ready",
    "priced",
}

BLOCKED_STATES = {
    "blocked",
    "failed",
    "rejected",
    "error",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, max_length: int = 400) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def _safe_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace("R", "").replace(",", "").replace("%", "").strip()
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _contains_sensitive_marker(path: Path) -> bool:
    lowered = str(path).lower()
    return any(marker in lowered for marker in SENSITIVE_PATH_MARKERS)


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def _modified_at(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return ""


def _file_metadata(path: Path) -> Dict[str, Any]:
    try:
        stat = path.stat()
        size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    except OSError:
        size = 0
        modified = ""

    return {
        "path": _relative_path(path),
        "name": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": size,
        "modified_at": modified,
    }


def _source_status(path: Path, source_type: str) -> Dict[str, Any]:
    try:
        size = path.stat().st_size if path.exists() and path.is_file() else 0
    except OSError:
        size = 0

    return {
        "source": _relative_path(path),
        "type": source_type,
        "exists": path.exists(),
        "is_file": path.is_file(),
        "size_bytes": size,
        "readable": path.exists() and path.is_file() and size <= MAX_JSON_BYTES and not _contains_sensitive_marker(path),
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


def _directory_status(name: str, directory: Path) -> Dict[str, Any]:
    files, limit_reached = _iter_safe_files(directory)
    doc_count = sum(1 for path in files if path.suffix.lower() in SAFE_DOC_EXTENSIONS)
    json_count = sum(1 for path in files if path.suffix.lower() == ".json")

    return {
        "source": name,
        "path": _relative_path(directory),
        "type": "directory",
        "exists": directory.exists(),
        "is_dir": directory.is_dir(),
        "scanned_files": len(files),
        "doc_artifact_count": doc_count,
        "json_file_count": json_count,
        "scan_limit_reached": limit_reached,
    }


def _read_json(path: Path) -> Tuple[Optional[Any], Dict[str, Any]]:
    status = _source_status(path, "json")
    if not status["readable"]:
        return None, status

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), {**status, "loaded": True}
    except (OSError, json.JSONDecodeError) as exc:
        return None, {**status, "loaded": False, "error": _safe_text(exc)}


def _slug(value: Any) -> str:
    text = _safe_text(value, 500).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _prettify_reference(value: str) -> str:
    clean = re.sub(r"__lmcp.*$", "", value, flags=re.IGNORECASE)
    clean = clean.replace("_", " ").replace("-", " ")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean or value


def _quote_reference_from_group(group: Path) -> str:
    name = group.name
    if "__LMCP-" in name:
        return name.split("__LMCP-", 1)[0]
    if "__LMCP_" in name:
        return name.split("__LMCP_", 1)[0]
    return name


def _first_value(record: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _nested_value(record: Dict[str, Any], parent_key: str, keys: Iterable[str]) -> Any:
    parent = record.get(parent_key)
    if not isinstance(parent, dict):
        return None
    return _first_value(parent, keys)


def _estimated_profit(record: Dict[str, Any]) -> Optional[float]:
    direct = _safe_number(_first_value(record, ("estimated_profit", "profit", "expected_profit")))
    if direct is not None:
        return direct
    return _safe_number(_nested_value(record, "pricing_result", ("estimated_profit", "existing_profit")))


def _margin_percent(record: Dict[str, Any]) -> Optional[float]:
    direct = _safe_number(_first_value(record, ("margin_percent", "estimated_margin", "estimated_margin_percent")))
    if direct is None:
        direct = _safe_number(_nested_value(record, "pricing_result", ("estimated_margin_percent", "existing_margin_percent")))
    if direct is not None and 0 < direct <= 1:
        return round(direct * 100, 2)
    return direct


def _estimated_value(record: Dict[str, Any], estimated_profit: Optional[float], margin_percent: Optional[float]) -> Optional[float]:
    direct = _safe_number(
        _first_value(
            record,
            (
                "estimated_value",
                "contract_value",
                "tender_value",
                "value",
                "estimated_contract_value",
            ),
        )
    )
    if direct is not None:
        return direct
    if estimated_profit is not None and margin_percent and margin_percent > 0:
        return round(estimated_profit / (margin_percent / 100), 2)
    return None


def _latest_activity(record: Dict[str, Any]) -> str:
    values = [
        _first_value(record, ("updated_at", "finished_at", "checked_at", "proof_timestamp", "created_at", "started_at")),
    ]
    audit_log = record.get("audit_log") or record.get("lifecycle_trace") or []
    if isinstance(audit_log, list):
        for event in audit_log[-5:]:
            if isinstance(event, dict):
                values.append(_first_value(event, ("at", "timestamp", "created_at")))

    safe_values = [_safe_text(value, 80) for value in values if value]
    return max(safe_values) if safe_values else ""


def _lifecycle_records() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    rfqs_path = SAFE_SOURCE_DIRS["runtime/rfq_lifecycle"] / "rfqs.json"
    data, status = _read_json(rfqs_path)
    records: List[Dict[str, Any]] = []
    index: Dict[str, Dict[str, Any]] = {}

    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, dict):
            for record_id, record in items.items():
                if not isinstance(record, dict):
                    continue
                normalized = {**record, "_record_id": str(record_id), "_latest_activity": _latest_activity(record)}
                records.append(normalized)
                for key_source in (
                    record_id,
                    record.get("rfq_id"),
                    record.get("title"),
                    record.get("quote_number"),
                    record.get("buyer_name"),
                ):
                    key = _slug(key_source)
                    if key and key not in index:
                        index[key] = normalized
        elif isinstance(items, list):
            for idx, record in enumerate(items):
                if not isinstance(record, dict):
                    continue
                record_id = _safe_text(_first_value(record, ("id", "rfq_id", "reference")) or f"rfq-{idx}")
                normalized = {**record, "_record_id": record_id, "_latest_activity": _latest_activity(record)}
                records.append(normalized)
                for key_source in (record_id, record.get("rfq_id"), record.get("title"), record.get("quote_number")):
                    key = _slug(key_source)
                    if key and key not in index:
                        index[key] = normalized

    return index, records, [status]


def _match_lifecycle(reference: str, title: str, index: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    keys = [_slug(reference), _slug(title)]
    for key in keys:
        if key in index:
            return index[key]

    for key in keys:
        if not key:
            continue
        for candidate_key, record in index.items():
            if key in candidate_key or candidate_key in key:
                return record

    return None


def _artifact_groups() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    groups: Dict[str, Dict[str, Any]] = {}
    source_statuses: List[Dict[str, Any]] = []

    for source_name, directory in SAFE_SOURCE_DIRS.items():
        files, limit_reached = _iter_safe_files(directory)
        doc_count = sum(1 for path in files if path.suffix.lower() in SAFE_DOC_EXTENSIONS)
        json_count = sum(1 for path in files if path.suffix.lower() == ".json")
        source_statuses.append(
            {
                "source": source_name,
                "path": _relative_path(directory),
                "type": "directory",
                "exists": directory.exists(),
                "is_dir": directory.is_dir(),
                "scanned_files": len(files),
                "doc_artifact_count": doc_count,
                "json_file_count": json_count,
                "scan_limit_reached": limit_reached,
            }
        )
        for path in files:
            suffix = path.suffix.lower()
            if suffix not in SAFE_DOC_EXTENSIONS:
                continue
            metadata = _file_metadata(path)
            group_path = path.parent
            group_key = _relative_path(group_path)
            group = groups.setdefault(
                group_key,
                {
                    "group_path": group_path,
                    "source": source_name,
                    "files": [],
                    "latest_activity": "",
                },
            )
            group["files"].append(metadata)
            if metadata["modified_at"] > group["latest_activity"]:
                group["latest_activity"] = metadata["modified_at"]

    return list(groups.values()), source_statuses


def _has_named_artifact(files: List[Dict[str, Any]], terms: Iterable[str], extensions: Optional[Iterable[str]] = None) -> bool:
    allowed_extensions = set(extensions or [])
    for file_info in files:
        name = _safe_text(file_info.get("name")).lower()
        extension = _safe_text(file_info.get("extension")).lower()
        if allowed_extensions and extension not in allowed_extensions:
            continue
        if any(term in name for term in terms):
            return True
    return False


def _lifecycle_has_document(record: Optional[Dict[str, Any]], terms: Iterable[str]) -> bool:
    if not record:
        return False
    paths = record.get("document_paths") or record.get("quote_pack_artifacts") or []
    if isinstance(paths, dict):
        paths = list(paths.values())
    if not isinstance(paths, list):
        return False
    lowered_terms = list(terms)
    for path in paths:
        text = _safe_text(path, 500).lower()
        if any(term in text for term in lowered_terms):
            return True
    return False


def _pricing_status(files: List[Dict[str, Any]], lifecycle: Optional[Dict[str, Any]]) -> str:
    if _has_named_artifact(files, ("pricing", "schedule", "rates", "price"), (".xlsx", ".xls", ".csv", ".pdf")):
        return "found"
    pricing_result = lifecycle.get("pricing_result") if lifecycle else None
    if isinstance(pricing_result, dict) and pricing_result.get("priced") is True:
        return "priced"
    return "missing"


def _boq_status(files: List[Dict[str, Any]], lifecycle: Optional[Dict[str, Any]]) -> str:
    if _has_named_artifact(files, ("boq", "bill-of-quantity", "bill_of_quantity", "bill of quantity"), (".xlsx", ".xls", ".csv", ".pdf")):
        return "found"
    if _lifecycle_has_document(lifecycle, ("boq", "bill-of-quantity", "bill_of_quantity", "bill of quantity")):
        return "source_document_found"
    return "missing"


def _sbd_status(files: List[Dict[str, Any]], lifecycle: Optional[Dict[str, Any]]) -> str:
    if _has_named_artifact(files, ("sbd", "standard-bidding", "standard bidding"), (".pdf", ".docx")):
        return "found"
    if _lifecycle_has_document(lifecycle, ("sbd", "standard-bidding", "standard bidding")):
        return "source_document_found"
    return "missing"


def _quote_status(files: List[Dict[str, Any]], lifecycle: Optional[Dict[str, Any]]) -> str:
    names = [_safe_text(file_info.get("name")).lower() for file_info in files]
    has_quote_pdf = any(
        name.endswith(".pdf")
        and "purchase_order" not in name
        and "award_summary" not in name
        and "portal_submission" not in name
        for name in names
    )
    if has_quote_pdf:
        return "generated"
    if lifecycle:
        state = _safe_text(lifecycle.get("current_state") or lifecycle.get("submission_status")).lower()
        if state:
            return state
    return "artifact_found"


def _missing_items(
    quote_status: str,
    pricing_schedule_status: str,
    boq_status: str,
    sbd_status: str,
) -> List[str]:
    missing: List[str] = []
    if quote_status not in READY_QUOTE_STATES and quote_status != "artifact_found":
        missing.append("generated_quote_file")
    if pricing_schedule_status == "missing":
        missing.append("pricing_schedule")
    if boq_status == "missing":
        missing.append("boq")
    if sbd_status == "missing":
        missing.append("sbd_returnable")
    return missing


def _readiness_score(
    quote_status: str,
    pricing_schedule_status: str,
    boq_status: str,
    sbd_status: str,
    missing_items: List[str],
) -> int:
    score = 0
    if quote_status in READY_QUOTE_STATES or quote_status == "artifact_found":
        score += 35
    if pricing_schedule_status in {"found", "priced"}:
        score += 25
    if boq_status in {"found", "source_document_found"}:
        score += 15
    if sbd_status in {"found", "source_document_found"}:
        score += 15
    if not missing_items:
        score += 10
    return min(score, 100)


def _recommended_next_step(quote_status: str, missing_items: List[str], risks: List[str]) -> str:
    if risks:
        return "Resolve quote pack risk before operator review"
    if "generated_quote_file" in missing_items:
        return "Review quote generation candidate"
    if "pricing_schedule" in missing_items or "boq" in missing_items:
        return "Attach pricing schedule or BOQ before quote pack review"
    if "sbd_returnable" in missing_items:
        return "Review SBD returnables before submission readiness"
    if quote_status in READY_QUOTE_STATES or quote_status == "artifact_found":
        return "Ready for operator quote pack review"
    return "Review quote pack readiness"


def _risks_from_lifecycle(lifecycle: Optional[Dict[str, Any]]) -> List[str]:
    if not lifecycle:
        return []
    risks: List[str] = []
    for key in ("failure_reason", "failure_classification", "validation_terminal_reason"):
        value = _safe_text(lifecycle.get(key), 220)
        if value and value.lower() not in {"none", "null"}:
            risks.append(value)
    state = _safe_text(lifecycle.get("current_state")).lower()
    if state in BLOCKED_STATES and not risks:
        risks.append(f"Lifecycle state is {state}")
    return risks[:8]


def _quote_record_from_group(group: Dict[str, Any], lifecycle_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    group_path = group["group_path"]
    reference = _quote_reference_from_group(group_path)
    title = _prettify_reference(reference)
    lifecycle = _match_lifecycle(reference, title, lifecycle_index)
    files = sorted(group["files"], key=lambda item: item.get("modified_at", ""), reverse=True)
    generated_files = [file_info["path"] for file_info in files]
    quote_status = _quote_status(files, lifecycle)
    pricing_schedule_status = _pricing_status(files, lifecycle)
    boq_status = _boq_status(files, lifecycle)
    sbd_status = _sbd_status(files, lifecycle)
    missing = _missing_items(quote_status, pricing_schedule_status, boq_status, sbd_status)
    returnables_status = "complete" if not missing else "incomplete"
    risks = _risks_from_lifecycle(lifecycle)
    estimated_profit = _estimated_profit(lifecycle or {})
    margin_percent = _margin_percent(lifecycle or {})
    estimated_value = _estimated_value(lifecycle or {}, estimated_profit, margin_percent)

    return {
        "id": _slug(_relative_path(group_path)) or _slug(reference),
        "rfq_reference": _safe_text(_first_value(lifecycle or {}, ("rfq_id", "reference")) or reference, 180),
        "title": _safe_text(_first_value(lifecycle or {}, ("title", "description")) or title, 500),
        "buyer": _safe_text(_first_value(lifecycle or {}, ("buyer", "buyer_name", "department", "procuring_entity")), 220),
        "province": _safe_text(_first_value(lifecycle or {}, ("province", "region", "location", "province_name")), 120),
        "quote_status": quote_status,
        "pricing_schedule_status": pricing_schedule_status,
        "boq_status": boq_status,
        "sbd_status": sbd_status,
        "returnables_status": returnables_status,
        "estimated_value": estimated_value,
        "estimated_profit": estimated_profit,
        "margin_percent": margin_percent,
        "quote_readiness_score": _readiness_score(quote_status, pricing_schedule_status, boq_status, sbd_status, missing),
        "missing_items": missing,
        "generated_files": generated_files[:20],
        "risks": risks,
        "recommended_next_step": _recommended_next_step(quote_status, missing, risks),
        "_latest_activity": group.get("latest_activity") or _latest_activity(lifecycle or {}),
        "_source_mode": "artifact_metadata",
    }


def _quote_record_from_lifecycle(record: Dict[str, Any]) -> Dict[str, Any]:
    pricing_result = record.get("pricing_result") if isinstance(record.get("pricing_result"), dict) else {}
    quote_artifacts = record.get("quote_pack_artifacts") or []
    if isinstance(quote_artifacts, dict):
        quote_artifacts = list(quote_artifacts.values())
    if not isinstance(quote_artifacts, list):
        quote_artifacts = []

    quote_status = "quote_pack_ready" if record.get("quote_pack_path") or quote_artifacts else _safe_text(record.get("current_state")).lower() or "candidate"
    pricing_schedule_status = "priced" if pricing_result.get("priced") is True else "missing"
    boq_status = "source_document_found" if _lifecycle_has_document(record, ("boq", "bill-of-quantity", "bill_of_quantity", "bill of quantity")) else "missing"
    sbd_status = "source_document_found" if _lifecycle_has_document(record, ("sbd", "standard-bidding", "standard bidding")) else "missing"
    missing = _missing_items(quote_status, pricing_schedule_status, boq_status, sbd_status)
    risks = _risks_from_lifecycle(record)
    estimated_profit = _estimated_profit(record)
    margin_percent = _margin_percent(record)
    estimated_value = _estimated_value(record, estimated_profit, margin_percent)
    reference = _safe_text(_first_value(record, ("rfq_id", "reference", "_record_id")) or "unknown-rfq", 180)

    return {
        "id": _slug(reference) or reference,
        "rfq_reference": reference,
        "title": _safe_text(_first_value(record, ("title", "description")) or reference, 500),
        "buyer": _safe_text(_first_value(record, ("buyer", "buyer_name", "department", "procuring_entity")), 220),
        "province": _safe_text(_first_value(record, ("province", "region", "location", "province_name")), 120),
        "quote_status": quote_status,
        "pricing_schedule_status": pricing_schedule_status,
        "boq_status": boq_status,
        "sbd_status": sbd_status,
        "returnables_status": "complete" if not missing else "incomplete",
        "estimated_value": estimated_value,
        "estimated_profit": estimated_profit,
        "margin_percent": margin_percent,
        "quote_readiness_score": _readiness_score(quote_status, pricing_schedule_status, boq_status, sbd_status, missing),
        "missing_items": missing,
        "generated_files": [_safe_text(item, 500) for item in quote_artifacts[:20]],
        "risks": risks,
        "recommended_next_step": _recommended_next_step(quote_status, missing, risks),
        "_latest_activity": record.get("_latest_activity", ""),
        "_source_mode": "rfq_lifecycle_runtime_fallback",
    }


def _strip_internal_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("_")}


def _load_quote_records() -> Dict[str, Any]:
    lifecycle_index, lifecycle_records, lifecycle_sources = _lifecycle_records()
    artifact_groups, source_statuses = _artifact_groups()
    records = [
        _quote_record_from_group(group, lifecycle_index)
        for group in artifact_groups
    ]
    runtime_fallback_used = False

    if not records:
        runtime_fallback_used = True
        records = [_quote_record_from_lifecycle(record) for record in lifecycle_records]

    deduped: Dict[str, Dict[str, Any]] = {}
    for record in records:
        key = record.get("id") or record.get("rfq_reference")
        if not key:
            continue
        existing = deduped.get(str(key))
        if not existing or record.get("_latest_activity", "") > existing.get("_latest_activity", ""):
            deduped[str(key)] = record

    sorted_records = sorted(
        deduped.values(),
        key=lambda item: item.get("_latest_activity") or "",
        reverse=True,
    )
    recent = [_strip_internal_fields(item) for item in sorted_records[:RECENT_LIMIT]]

    return {
        "records": sorted_records,
        "recent": recent,
        "sources_checked": source_statuses + lifecycle_sources,
        "runtime_fallback_used": runtime_fallback_used,
        "source_mode": "rfq_lifecycle_runtime_fallback" if runtime_fallback_used else "artifact_metadata",
    }


def _counts(records: List[Dict[str, Any]], recent_count: int) -> Dict[str, int]:
    ready = 0
    needs_pricing = 0
    missing_documents = 0
    blocked = 0

    for record in records:
        quote_status = _safe_text(record.get("quote_status")).lower()
        if record.get("quote_readiness_score", 0) >= 80:
            ready += 1
        if record.get("pricing_schedule_status") == "missing":
            needs_pricing += 1
        if record.get("missing_items"):
            missing_documents += 1
        if quote_status in BLOCKED_STATES or record.get("risks"):
            blocked += 1

    return {
        "total": len(records),
        "ready": ready,
        "needs_pricing": needs_pricing,
        "missing_documents": missing_documents,
        "blocked": blocked,
        "recent": recent_count,
    }


def _health_payload(loaded: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "domain": "quote_engine",
        "read_only": True,
        "timestamp": _timestamp(),
        "sources_checked": loaded["sources_checked"],
        "source_mode": loaded["source_mode"],
        "runtime_fallback_used": loaded["runtime_fallback_used"],
    }


def _status_payload(loaded: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "domain": "quote_engine",
        "counts": _counts(loaded["records"], len(loaded["recent"])),
        "read_only": True,
        "source_mode": loaded["source_mode"],
        "runtime_fallback_used": loaded["runtime_fallback_used"],
    }


def _recent_payload(loaded: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "items": loaded["recent"],
        "count": len(loaded["recent"]),
        "read_only": True,
        "source_mode": loaded["source_mode"],
        "runtime_fallback_used": loaded["runtime_fallback_used"],
    }


@router.get("/health")
def quotes_health() -> Dict[str, Any]:
    return _health_payload(_load_quote_records())


@router.get("/status")
def quotes_status() -> Dict[str, Any]:
    return _status_payload(_load_quote_records())


@router.get("/recent")
def quotes_recent() -> Dict[str, Any]:
    return _recent_payload(_load_quote_records())


@router.get("/summary")
def quotes_summary() -> Dict[str, Any]:
    loaded = _load_quote_records()
    health = _health_payload(loaded)
    status = _status_payload(loaded)
    recent = _recent_payload(loaded)
    return {
        "status": "ok",
        "domain": "quote_engine",
        "read_only": True,
        "timestamp": _timestamp(),
        "source_mode": loaded["source_mode"],
        "runtime_fallback_used": loaded["runtime_fallback_used"],
        "health": health,
        "status_summary": status,
        "recent_sample": recent["items"][:10],
        "recent_count": recent["count"],
    }
