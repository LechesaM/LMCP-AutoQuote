from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter


router = APIRouter(prefix="/api/rfq", tags=["stable-rfq"])

BASE_DIR = Path(__file__).resolve().parents[2]
MAX_JSON_BYTES = 10 * 1024 * 1024
RECENT_LIMIT = 50

SAFE_SOURCE_DIRS: Dict[str, Path] = {
    "runtime/rfq_lifecycle": BASE_DIR / "runtime" / "rfq_lifecycle",
    "runtime/portal_submission": BASE_DIR / "runtime" / "portal_submission",
    "monthly_quotes": BASE_DIR / "monthly_quotes",
}

PRIMARY_JSON_FILES: List[Path] = [
    SAFE_SOURCE_DIRS["runtime/rfq_lifecycle"] / "rfqs.json",
    SAFE_SOURCE_DIRS["runtime/rfq_lifecycle"] / "mission_control_snapshot.json",
    SAFE_SOURCE_DIRS["runtime/rfq_lifecycle"] / "analytics.json",
    SAFE_SOURCE_DIRS["runtime/portal_submission"] / "portal_submission_history.json",
    SAFE_SOURCE_DIRS["runtime/portal_submission"] / "latest_quote_discovery_for_final.json",
]

SENSITIVE_PATH_MARKERS = (
    ".env",
    "secret",
    "credential",
    "password",
    "token",
    "cookie",
    "storage_state",
)

QUALIFIED_STATES = {
    "QUALIFIED",
    "DOCUMENTS_ACQUIRED",
    "DOCUMENTS_PARSED",
    "PRICED",
    "QUOTE_PACK_READY",
    "SUBMISSION_READY",
    "PROOF_CAPTURED",
    "COMPLETED",
}

BLOCKED_STATES = {
    "BLOCKED",
    "FAILED",
    "REJECTED",
    "ERROR",
    "DEAD_LETTER",
}

REVIEW_STATES = {
    "REVIEW_REQUIRED",
    "READY_FOR_RETRY",
    "MANUAL_REVIEW",
    "ASSISTED_REQUIRED",
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


def _source_status(path: Path, source_type: str) -> Dict[str, Any]:
    try:
        size = path.stat().st_size if path.exists() and path.is_file() else 0
    except OSError:
        size = 0

    return {
        "source": str(path.relative_to(BASE_DIR)) if path.is_absolute() else str(path),
        "type": source_type,
        "exists": path.exists(),
        "is_file": path.is_file(),
        "size_bytes": size,
        "readable": path.exists() and path.is_file() and size <= MAX_JSON_BYTES and not _contains_sensitive_marker(path),
    }


def _discover_sources() -> List[Path]:
    discovered: List[Path] = []
    seen = set()

    for path in PRIMARY_JSON_FILES:
        if path not in seen:
            discovered.append(path)
            seen.add(path)

    for directory in SAFE_SOURCE_DIRS.values():
        if not directory.exists() or not directory.is_dir():
            continue
        try:
            for path in sorted(directory.rglob("*.json")):
                if len(discovered) >= 100:
                    break
                if path in seen or _contains_sensitive_marker(path):
                    continue
                discovered.append(path)
                seen.add(path)
        except OSError:
            continue

    return discovered


def _read_json(path: Path) -> Tuple[Optional[Any], Dict[str, Any]]:
    status = _source_status(path, "json")
    if not status["readable"]:
        return None, status

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), {**status, "loaded": True}
    except (OSError, json.JSONDecodeError) as exc:
        return None, {**status, "loaded": False, "error": _safe_text(exc)}


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


def _latest_activity(record: Dict[str, Any]) -> str:
    candidates = [
        _first_value(
            record,
            (
                "updated_at",
                "finished_at",
                "checked_at",
                "proof_timestamp",
                "created_at",
                "started_at",
                "last_seen",
            ),
        )
    ]

    audit_log = record.get("audit_log") or record.get("lifecycle_trace") or []
    if isinstance(audit_log, list):
        for event in audit_log[-5:]:
            if isinstance(event, dict):
                candidates.append(_first_value(event, ("at", "timestamp", "created_at")))

    values = [_safe_text(value, 80) for value in candidates if value]
    return max(values) if values else ""


def _closing_date(record: Dict[str, Any]) -> str:
    explicit = _first_value(
        record,
        (
            "closing_date",
            "closingDate",
            "closing",
            "deadline",
            "tender_closing_date",
            "briefing_or_closing_date",
        ),
    )
    if explicit:
        return _safe_text(explicit, 120)

    title = _safe_text(record.get("title"), 800)
    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", title)
    if not match:
        return ""

    day, month, year = match.groups()
    try:
        parsed = datetime(int(year), int(month), int(day))
        return parsed.date().isoformat()
    except ValueError:
        return match.group(0)


def _status(record: Dict[str, Any]) -> str:
    value = _first_value(record, ("current_state", "status", "submission_status", "state"))
    return _safe_text(value, 120) or "UNKNOWN"


def _estimated_profit(record: Dict[str, Any]) -> Optional[float]:
    direct = _safe_number(_first_value(record, ("estimated_profit", "profit", "expected_profit")))
    if direct is not None:
        return direct
    nested = _safe_number(_nested_value(record, "pricing_result", ("estimated_profit", "existing_profit")))
    return nested


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


def _risks(record: Dict[str, Any]) -> List[str]:
    risks: List[str] = []
    raw_risks = record.get("risks") or record.get("blockers") or []
    if isinstance(raw_risks, list):
        risks.extend(_safe_text(item, 220) for item in raw_risks if item)
    elif raw_risks:
        risks.append(_safe_text(raw_risks, 220))

    for key in ("failure_reason", "failure_classification", "validation_terminal_reason"):
        value = _safe_text(record.get(key), 220)
        if value and value.lower() not in {"none", "null"}:
            risks.append(value)

    status = _status(record).upper()
    if any(marker in status for marker in BLOCKED_STATES) and not risks:
        risks.append(f"Lifecycle state is {status}")

    deduped: List[str] = []
    seen = set()
    for risk in risks:
        if risk and risk not in seen:
            deduped.append(risk)
            seen.add(risk)
    return deduped[:8]


def _recommended_action(record: Dict[str, Any]) -> str:
    explicit = _safe_text(record.get("recommended_action") or record.get("recommended_next_step"), 220)
    if explicit:
        return explicit

    status = _status(record).upper()
    if status in BLOCKED_STATES or _risks(record):
        return "Review blocker before quote progression"
    if status in REVIEW_STATES or "REVIEW" in status:
        return "Operator review required"
    if status in {"SUBMISSION_READY", "PROOF_CAPTURED", "COMPLETED"}:
        return "Monitor submission readiness and proof state"
    if status in QUALIFIED_STATES:
        return "Continue quote preparation workflow"
    return "Review RFQ qualification"


def _normalize_record(record_id: str, record: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    estimated_profit = _estimated_profit(record)
    margin_percent = _margin_percent(record)
    estimated_value = _estimated_value(record, estimated_profit, margin_percent)
    reference = _safe_text(
        _first_value(
            record,
            (
                "reference",
                "buyer_rfq_number",
                "rfq_number",
                "rfq_reference",
                "rfq_id",
                "quote_number",
            ),
        )
        or record_id,
        180,
    )

    return {
        "id": _safe_text(_first_value(record, ("id", "rfq_id")) or record_id, 180),
        "reference": reference,
        "title": _safe_text(_first_value(record, ("title", "description", "name")) or reference, 500),
        "buyer": _safe_text(_first_value(record, ("buyer", "buyer_name", "department", "procuring_entity")), 220),
        "province": _safe_text(_first_value(record, ("province", "region", "location", "province_name")), 120),
        "source": _safe_text(_first_value(record, ("source", "portal", "portal_domain")) or source_file, 220),
        "closing_date": _closing_date(record),
        "status": _status(record),
        "estimated_value": estimated_value,
        "estimated_profit": estimated_profit,
        "margin_percent": margin_percent,
        "qualification_score": _safe_number(_first_value(record, ("qualification_score", "score", "readiness_score"))),
        "risks": _risks(record),
        "recommended_action": _recommended_action(record),
        "_latest_activity": _latest_activity(record),
        "_source_file": source_file,
    }


def _items_from_lifecycle(data: Any, source_file: str) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []

    items = data.get("items")
    records: List[Dict[str, Any]] = []
    if isinstance(items, dict):
        for record_id, record in items.items():
            if isinstance(record, dict):
                records.append(_normalize_record(str(record_id), record, source_file))
    elif isinstance(items, list):
        for index, record in enumerate(items):
            if isinstance(record, dict):
                record_id = _safe_text(_first_value(record, ("id", "rfq_id", "reference")) or f"item-{index}")
                records.append(_normalize_record(record_id, record, source_file))

    return records


def _items_from_portal_history(data: Any, source_file: str) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        return []

    records: List[Dict[str, Any]] = []
    for index, record in enumerate(data):
        if not isinstance(record, dict):
            continue
        reference = _safe_text(_first_value(record, ("buyer_rfq_number", "rfq_reference", "quote_number")) or f"portal-{index}")
        flattened = {
            **record,
            "rfq_id": reference,
            "title": record.get("title") or reference,
            "buyer_name": record.get("buyer") or record.get("portal_domain") or _nested_value(record, "route", ("portal_domain",)),
            "source": record.get("source") or _nested_value(record, "route", ("portal_domain", "route")),
        }
        records.append(_normalize_record(reference, flattened, source_file))
    return records


def _items_from_quote_discovery(data: Any, source_file: str) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    reference = _safe_text(_first_value(data, ("buyer_rfq_number", "rfq_reference", "quote_number")) or "latest-quote-discovery")
    return [_normalize_record(reference, data, source_file)]


def _strip_internal_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("_")}


def _load_runtime_records() -> Dict[str, Any]:
    directory_statuses: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []

    for name, directory in SAFE_SOURCE_DIRS.items():
        directory_statuses.append(
            {
                "source": name,
                "type": "directory",
                "exists": directory.exists(),
                "is_dir": directory.is_dir(),
            }
        )

    discovered_sources = _discover_sources()
    source_statuses: Dict[str, Dict[str, Any]] = {
        str(path): _source_status(path, "json")
        for path in discovered_sources
    }

    def read_candidate(path: Path) -> Optional[Any]:
        data, source_status = _read_json(path)
        source_statuses[str(path)] = source_status
        return data

    for path in discovered_sources:
        if path.name != "rfqs.json":
            continue
        data = read_candidate(path)
        if data is not None:
            source_file = str(path.relative_to(BASE_DIR))
            records.extend(_items_from_lifecycle(data, source_file))

    if not records:
        for path in discovered_sources:
            if path.name != "portal_submission_history.json":
                continue
            data = read_candidate(path)
            if data is not None:
                records.extend(_items_from_portal_history(data, str(path.relative_to(BASE_DIR))))

    if not records:
        for path in discovered_sources:
            if path.name != "latest_quote_discovery_for_final.json":
                continue
            data = read_candidate(path)
            if data is not None:
                records.extend(_items_from_quote_discovery(data, str(path.relative_to(BASE_DIR))))

    deduped: Dict[str, Dict[str, Any]] = {}
    for item in records:
        key = item.get("id") or item.get("reference")
        if not key:
            continue
        existing = deduped.get(str(key))
        if not existing or item.get("_latest_activity", "") > existing.get("_latest_activity", ""):
            deduped[str(key)] = item

    sorted_records = sorted(
        deduped.values(),
        key=lambda item: item.get("_latest_activity") or "",
        reverse=True,
    )

    latest_activity = sorted_records[0].get("_latest_activity", "") if sorted_records else ""
    recent = [_strip_internal_fields(item) for item in sorted_records[:RECENT_LIMIT]]

    return {
        "records": sorted_records,
        "recent": recent,
        "latest_activity": latest_activity,
        "sources_checked": directory_statuses + list(source_statuses.values()),
        "runtime_fallback_used": True,
    }


def _counts(records: List[Dict[str, Any]], recent_count: int) -> Dict[str, int]:
    qualified = 0
    blocked = 0
    review_required = 0

    for record in records:
        state = _safe_text(record.get("status")).upper()
        if state in QUALIFIED_STATES:
            qualified += 1
        if state in BLOCKED_STATES or any(marker in state for marker in BLOCKED_STATES):
            blocked += 1
        if state in REVIEW_STATES or "REVIEW" in state:
            review_required += 1

    return {
        "total": len(records),
        "recent": recent_count,
        "qualified": qualified,
        "blocked": blocked,
        "review_required": review_required,
    }


def _health_payload(loaded: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "domain": "rfq_engine",
        "read_only": True,
        "timestamp": _timestamp(),
        "sources_checked": loaded["sources_checked"],
        "source_mode": "runtime_json_fallback",
        "runtime_fallback_used": loaded["runtime_fallback_used"],
    }


def _status_payload(loaded: Dict[str, Any]) -> Dict[str, Any]:
    records = loaded["records"]
    return {
        "status": "ok",
        "domain": "rfq_engine",
        "counts": _counts(records, len(loaded["recent"])),
        "latest_activity": loaded["latest_activity"],
        "read_only": True,
        "source_mode": "runtime_json_fallback",
        "runtime_fallback_used": loaded["runtime_fallback_used"],
    }


def _recent_payload(loaded: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "items": loaded["recent"],
        "count": len(loaded["recent"]),
        "read_only": True,
        "source_mode": "runtime_json_fallback",
        "runtime_fallback_used": loaded["runtime_fallback_used"],
    }


@router.get("/health")
def rfq_health() -> Dict[str, Any]:
    return _health_payload(_load_runtime_records())


@router.get("/status")
def rfq_status() -> Dict[str, Any]:
    return _status_payload(_load_runtime_records())


@router.get("/recent")
def rfq_recent() -> Dict[str, Any]:
    return _recent_payload(_load_runtime_records())


@router.get("/summary")
def rfq_summary() -> Dict[str, Any]:
    loaded = _load_runtime_records()
    health = _health_payload(loaded)
    status = _status_payload(loaded)
    recent = _recent_payload(loaded)
    return {
        "status": "ok",
        "domain": "rfq_engine",
        "read_only": True,
        "timestamp": _timestamp(),
        "source_mode": "runtime_json_fallback",
        "runtime_fallback_used": loaded["runtime_fallback_used"],
        "health": health,
        "status_summary": status,
        "recent_sample": recent["items"][:10],
        "recent_count": recent["count"],
    }
