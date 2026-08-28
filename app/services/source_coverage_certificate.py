from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "app" / "data" / "harvest_sources.json"
DEFAULT_RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "source_coverage"
LATEST_PATH = DEFAULT_RUNTIME_ROOT / "latest.json"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_date(value: Optional[str] = None) -> str:
    if value:
        return value[:10]
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _safe_write_text(path: Path, text: str) -> None:
    _ensure_parent(path)
    temporary = path.with_name(".%s.%s.tmp" % (path.name, uuid.uuid4().hex))
    temporary.write_text(text, encoding="utf-8")
    os.replace(str(temporary), str(path))


def _safe_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _safe_write_text(path, json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")


def _git_commit() -> Optional[str]:
    if "LMCP_GIT_COMMIT" in os.environ:
        commit = os.environ.get("LMCP_GIT_COMMIT", "").strip()
        return commit or None
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return None
    commit = completed.stdout.strip()
    return commit or None


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _as_sequence(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    return [value]


def _source_name(source: Mapping[str, Any], fallback_index: int) -> str:
    for key in ("source_name", "name", "title", "label", "id"):
        value = source.get(key)
        if value:
            return str(value)
    if source.get("url"):
        return str(source["url"])
    return "source-%d" % (fallback_index + 1)


def _source_url(source: Mapping[str, Any]) -> Optional[str]:
    for key in ("source_url", "url", "href", "uri"):
        value = source.get(key)
        if value:
            return str(value)
    return None


def _source_type(source: Mapping[str, Any]) -> Optional[str]:
    for key in ("source_type", "type", "group", "category", "portal_type"):
        value = source.get(key)
        if value:
            return str(value)
    return None


def _source_identity(source: Mapping[str, Any], fallback_index: int = 0) -> str:
    for key in (
        "registry_id",
        "source_identity",
        "source_id",
        "source_key",
        "registry_key",
        "key",
        "id",
        "uuid",
    ):
        value = source.get(key)
        if value:
            return str(value)
    url = _source_url(source)
    name = _source_name(source, fallback_index)
    if url:
        parsed = urlsplit(url)
        canonical_url = "%s://%s%s" % (parsed.scheme, parsed.netloc, parsed.path)
        canonical_url = canonical_url.rstrip("/")
        if canonical_url:
            return "%s::%s" % (canonical_url, name)
    return name or "source-%d" % (fallback_index + 1)


def _source_enabled(source: Mapping[str, Any]) -> bool:
    for key in ("enabled", "is_enabled", "active", "selected_for_run"):
        if key in source:
            return _coerce_bool(source.get(key), default=True)
    return True


def _record_has_explicit_outcome(record: Mapping[str, Any]) -> bool:
    return any(
        key in record
        for key in ("success", "error_reason", "failure_reason", "error", "http_status", "status_code", "completed_at", "response_time_ms", "response_time_seconds")
    )


def _normalise_registry_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, Mapping):
        for key in ("sources", "items", "entries", "registry"):
            if key in payload:
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError("Registry payload must be a list or contain a list under sources/items/entries/registry.")
    records: List[Dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            continue
        record = dict(item)
        record.setdefault("source_name", _source_name(record, index))
        record.setdefault("source_url", _source_url(record))
        record.setdefault("source_type", _source_type(record))
        record.setdefault("enabled", _source_enabled(record))
        records.append(record)
    return records


def resolve_registry_path(explicit: Optional[str] = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    env_path = os.environ.get("LMCP_HARVEST_SOURCES_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return DEFAULT_REGISTRY_PATH


def load_registry_entries(path: Optional[str] = None) -> List[Dict[str, Any]]:
    registry_path = resolve_registry_path(path)
    if not registry_path.exists():
        raise FileNotFoundError("Source registry not found: %s" % registry_path)
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    return _normalise_registry_payload(payload)


def registry_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    total = len(entries)
    enabled = sum(1 for entry in entries if _source_enabled(entry))
    return {"registry_total": total, "enabled_sources": enabled, "disabled_sources": total - enabled}


@dataclass
class SourceCoverageRecord:
    source_name: str
    source_identity: str = ""
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    source_group: Optional[str] = None
    enabled: bool = True
    selected: bool = False
    attempted: bool = False
    success: bool = False
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    response_time_ms: Optional[float] = None
    http_status: Optional[Any] = None
    candidates_found: Optional[int] = None
    qualifying_candidates: Optional[int] = None
    error_reason: Optional[str] = None
    run_id: Optional[str] = None
    explicit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = dataclasses.asdict(self)
        payload.pop("explicit", None)
        return payload


@dataclass
class SourceCoverageSummary:
    run_id: str
    started_at: str
    completed_at: str
    git_commit: Optional[str]
    registry_total: int
    enabled_sources: int
    disabled_sources: int
    selected_sources: int
    attempted_sources: int
    successful_sources: int
    failed_sources: int
    skipped_sources: int
    unique_sources_checked: int
    not_checked: int
    coverage_percentage: float
    candidates_found: int
    qualifying_opportunities_found: int
    documents_found: int
    documents_downloaded: int
    execution_mode: str
    full_sweep_requested: bool
    coverage_status: str
    source_results_path: str
    summary_path: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _extract_explicit_records(run_result: Mapping[str, Any]) -> List[Dict[str, Any]]:
    for key in ("source_results", "sources", "results", "source_results_jsonl"):
        value = run_result.get(key)
        if not value:
            continue
        records: List[Dict[str, Any]] = []
        for index, item in enumerate(_as_sequence(value)):
            if isinstance(item, Mapping):
                record = dict(item)
                record.setdefault("source_name", _source_name(record, index))
                record.setdefault("source_url", _source_url(record))
                record.setdefault("source_type", _source_type(record))
                record.setdefault("source_identity", _source_identity(record, index))
                record.setdefault("enabled", _coerce_bool(record.get("enabled"), True))
                record.setdefault("selected", _coerce_bool(record.get("selected")))
                record.setdefault("attempted", _coerce_bool(record.get("attempted")))
                record.setdefault("success", _coerce_bool(record.get("success")))
                record["explicit"] = True
                records.append(record)
        if records:
            return records
    return []


def _extract_name_set(value: Any) -> Set[str]:
    names: Set[str] = set()
    for item in _as_sequence(value):
        if isinstance(item, Mapping):
            name = _source_name(item, len(names))
            if name:
                names.add(name)
            continue
        text = str(item).strip()
        if text:
            names.add(text)
    return names


def _normalise_source_results(
    run_result: Mapping[str, Any],
    registry_entries: Sequence[Mapping[str, Any]],
) -> List[SourceCoverageRecord]:
    explicit_records = _extract_explicit_records(run_result)
    explicit_by_name = {record["source_name"]: record for record in explicit_records}
    explicit_by_identity = {
        str(record.get("source_identity") or record["source_name"]): record
        for record in explicit_records
    }
    selected_names = _extract_name_set(run_result.get("selected_sources"))
    attempted_names = _extract_name_set(run_result.get("attempted_sources"))
    successful_names = _extract_name_set(run_result.get("successful_sources"))
    failed_names = _extract_name_set(run_result.get("failed_sources"))
    skipped_names = _extract_name_set(run_result.get("skipped_sources"))
    records: List[SourceCoverageRecord] = []

    registry_map_by_name = {_source_name(entry, index): entry for index, entry in enumerate(registry_entries)}
    registry_map_by_identity = {
        _source_identity(entry, index): entry
        for index, entry in enumerate(registry_entries)
    }
    source_names = [_source_name(entry, index) for index, entry in enumerate(registry_entries)]
    source_names.extend(sorted(selected_names | attempted_names | successful_names | failed_names | skipped_names))
    source_names = list(dict.fromkeys(source_names))

    for name in source_names:
        base = registry_map_by_name.get(name, {})
        explicit = explicit_by_name.get(name, explicit_by_identity.get(name, {}))
        attempted = _coerce_bool(
            explicit.get("attempted"),
            default=name in attempted_names or name in successful_names or name in failed_names or name in selected_names,
        )
        success = _coerce_bool(explicit.get("success"), default=name in successful_names)
        selected = _coerce_bool(explicit.get("selected"), default=name in selected_names)
        enabled = _coerce_bool(explicit.get("enabled"), default=_source_enabled(base) if base else True)
        error_reason = explicit.get("error_reason") or explicit.get("failure_reason") or explicit.get("error")
        if error_reason is not None:
            error_reason = str(error_reason)
        records.append(
            SourceCoverageRecord(
                source_identity=str(
                    explicit.get("source_identity")
                    or _source_identity(explicit or base or {"source_name": name}, 0)
                    or _source_identity(registry_map_by_identity.get(name, {}) or {"source_name": name}, 0)
                ),
                source_name=name,
                source_url=explicit.get("source_url") or _source_url(base),
                source_type=explicit.get("source_type") or _source_type(base),
                source_group=(
                    explicit.get("source_group")
                    or explicit.get("category_group")
                    or base.get("source_group")
                    or base.get("category_group")
                ),
                enabled=enabled,
                selected=selected,
                attempted=attempted,
                success=success,
                started_at=explicit.get("started_at"),
                completed_at=explicit.get("completed_at"),
                response_time_ms=(
                    explicit.get("response_time_ms")
                    if explicit.get("response_time_ms") is not None
                    else explicit.get("response_time_seconds")
                ),
                http_status=(
                    explicit.get("http_status")
                    if explicit.get("http_status") is not None
                    else explicit.get("status_code")
                ),
                candidates_found=explicit.get("candidates_found"),
                qualifying_candidates=explicit.get("qualifying_candidates"),
                error_reason=error_reason,
                run_id=str(explicit.get("run_id") or run_result.get("run_id") or ""),
                explicit=bool(explicit),
            )
        )
    return records


def _source_summary_counts(records: Sequence[SourceCoverageRecord]) -> Dict[str, int]:
    enabled_records = [record for record in records if record.enabled]
    selected = [record for record in enabled_records if record.selected]
    attempted = [record for record in enabled_records if record.attempted]
    successful = [record for record in attempted if record.success]
    failed = [record for record in attempted if not record.success]
    # This is a count of unattempted *normalised records*.  Registry entries
    # can share a source name and are normalised into one record, so it is not
    # the coverage denominator and must never be displayed as NOT CHECKED.
    skipped = [record for record in enabled_records if not record.attempted]
    return {
        "selected_sources": len(selected),
        "attempted_sources": len(attempted),
        "successful_sources": len(successful),
        "failed_sources": len(failed),
        "skipped_sources": len(skipped),
        "unique_sources_checked": len({record.source_identity or record.source_name for record in attempted}),
        "candidates_found": sum(int(record.candidates_found or 0) for record in records),
        "qualifying_opportunities_found": sum(int(record.qualifying_candidates or 0) for record in records),
        "documents_found": int(sum(int(record.candidates_found or 0) for record in records)),
        "documents_downloaded": int(sum(int(record.qualifying_candidates or 0) for record in records)),
    }


def classify_coverage(
    *,
    enabled_sources: int,
    unique_sources_checked: int,
    attempted_sources: int,
    records: Sequence[SourceCoverageRecord],
    registry_entries: Sequence[Mapping[str, Any]],
    explicit_records: Sequence[Mapping[str, Any]],
    full_sweep_requested: bool,
    completed_at: Optional[str],
    explicit_run_completeness: Optional[bool] = None,
) -> str:
    if enabled_sources <= 0:
        return "FULL" if full_sweep_requested else "PARTIAL"
    if unique_sources_checked < 0 or attempted_sources < 0:
        return "FAILED"
    if explicit_run_completeness is False or not completed_at:
        return "FAILED"

    attempted_enabled = [record for record in records if record.enabled and record.attempted]
    explicit_enabled_records = [record for record in explicit_records if _coerce_bool(record.get("enabled"), True)]
    enabled_names = {_source_name(entry, index) for index, entry in enumerate(registry_entries) if _source_enabled(entry)}
    explicit_enabled_names = {_source_name(record, index) for index, record in enumerate(explicit_enabled_records)}

    if (
        full_sweep_requested
        and len(enabled_names) == enabled_sources
        and explicit_enabled_names == enabled_names
        and len(attempted_enabled) == enabled_sources
        and len(explicit_enabled_records) == enabled_sources
        and all(record.explicit for record in attempted_enabled)
    ):
        return "FULL"

    if attempted_sources == 0 and unique_sources_checked == 0:
        return "FAILED" if not completed_at else "PARTIAL"
    return "PARTIAL"


def build_run_summary(
    run_result: Mapping[str, Any],
    *,
    registry_path: Optional[str] = None,
    runtime_root: Optional[str] = None,
    git_commit: Optional[str] = None,
) -> Tuple[SourceCoverageSummary, List[SourceCoverageRecord]]:
    registry_entries = load_registry_entries(registry_path)
    registry_counts_map = registry_counts(registry_entries)
    explicit_records = _extract_explicit_records(run_result)
    records = _normalise_source_results(run_result, registry_entries)
    counts = _source_summary_counts(records)
    run_id = str(run_result.get("run_id") or "source-coverage-%s-%s" % (utc_now_iso().replace(":", "").replace("-", ""), uuid.uuid4().hex[:8]))
    started_at = str(run_result.get("started_at") or run_result.get("started") or run_result.get("run_started_at") or utc_now_iso())
    completed_at = str(run_result.get("completed_at") or run_result.get("completed") or run_result.get("run_completed_at") or "")
    # Some legacy harvest entry points report a terminal aggregate outcome but
    # do not include timestamps.  That is evidence of a completed run, even
    # though it cannot establish source-level coverage; classify it as PARTIAL
    # rather than FAILED.  Hooked entry points still supply real timings.
    terminal_statuses = {"ok", "success", "succeeded", "completed", "complete"}
    terminal_status = str(run_result.get("status") or run_result.get("harvest_status") or "").strip().lower()
    if not completed_at and terminal_status in terminal_statuses:
        completed_at = utc_now_iso()
    execution_mode = str(run_result.get("execution_mode") or run_result.get("mode") or "unknown")
    full_sweep_requested = _coerce_bool(run_result.get("full_sweep_requested"), False)
    explicit_complete = run_result.get("complete") if "complete" in run_result else run_result.get("run_complete")
    coverage_status = classify_coverage(
        enabled_sources=registry_counts_map["enabled_sources"],
        unique_sources_checked=counts["unique_sources_checked"],
        attempted_sources=counts["attempted_sources"],
        records=records,
        registry_entries=registry_entries,
        explicit_records=explicit_records,
        full_sweep_requested=full_sweep_requested,
        completed_at=completed_at or None,
        explicit_run_completeness=explicit_complete if isinstance(explicit_complete, bool) else None,
    )
    coverage_percentage = round(
        (counts["unique_sources_checked"] / registry_counts_map["enabled_sources"] * 100.0)
        if registry_counts_map["enabled_sources"]
        else 100.0,
        2,
    )
    summary = SourceCoverageSummary(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at or utc_now_iso(),
        git_commit=git_commit or _git_commit(),
        registry_total=registry_counts_map["registry_total"],
        enabled_sources=registry_counts_map["enabled_sources"],
        disabled_sources=registry_counts_map["disabled_sources"],
        selected_sources=counts["selected_sources"],
        attempted_sources=counts["attempted_sources"],
        successful_sources=counts["successful_sources"],
        failed_sources=counts["failed_sources"],
        skipped_sources=counts["skipped_sources"],
        unique_sources_checked=counts["unique_sources_checked"],
        not_checked=max(0, registry_counts_map["enabled_sources"] - counts["unique_sources_checked"]),
        coverage_percentage=coverage_percentage,
        candidates_found=counts["candidates_found"],
        qualifying_opportunities_found=counts["qualifying_opportunities_found"],
        documents_found=counts["documents_found"],
        documents_downloaded=counts["documents_downloaded"],
        execution_mode=execution_mode,
        full_sweep_requested=full_sweep_requested,
        coverage_status=coverage_status,
        source_results_path="",
        summary_path="",
    )
    return summary, records


def _run_directory(date_value: str, run_id: str, runtime_root: Optional[str] = None) -> Path:
    base = Path(runtime_root).expanduser().resolve() if runtime_root else DEFAULT_RUNTIME_ROOT
    return base / date_value / run_id


def write_run_certificate(
    run_result: Mapping[str, Any],
    *,
    registry_path: Optional[str] = None,
    runtime_root: Optional[str] = None,
    git_commit: Optional[str] = None,
) -> SourceCoverageSummary:
    summary, records = build_run_summary(
        run_result,
        registry_path=registry_path,
        runtime_root=runtime_root,
        git_commit=git_commit,
    )
    run_dir = _run_directory(_utc_date(summary.completed_at), summary.run_id, runtime_root)
    run_dir.mkdir(parents=True, exist_ok=True)
    source_results_path = run_dir / "source_results.jsonl"
    summary_path = run_dir / "coverage_summary.json"
    source_results_text = "\n".join(json.dumps(record.to_dict(), sort_keys=True) for record in records) + ("\n" if records else "")
    _safe_write_text(source_results_path, source_results_text)
    summary.source_results_path = str(source_results_path)
    summary.summary_path = str(summary_path)
    _safe_write_json(summary_path, summary.to_dict())
    latest_path = DEFAULT_RUNTIME_ROOT / "latest.json" if runtime_root is None else Path(runtime_root).expanduser().resolve() / "latest.json"
    _safe_write_json(latest_path, summary.to_dict())
    update_daily_coverage(_utc_date(summary.completed_at), runtime_root=runtime_root)
    return summary


def _read_run_summaries(day_dir: Path) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    if not day_dir.exists():
        return summaries
    for summary_path in sorted(day_dir.glob("*/coverage_summary.json")):
        try:
            summaries.append(json.loads(summary_path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return summaries


def update_daily_coverage(
    date_value: str,
    *,
    runtime_root: Optional[str] = None,
) -> Dict[str, Any]:
    base = Path(runtime_root).expanduser().resolve() if runtime_root else DEFAULT_RUNTIME_ROOT
    day_dir = base / date_value
    summaries = _read_run_summaries(day_dir)
    registry_total = 0
    enabled_registry_count = 0
    attempted_sources: Dict[str, Dict[str, Any]] = {}
    successful_sources: Dict[str, Dict[str, Any]] = {}
    failed_sources: Dict[str, Dict[str, Any]] = {}
    qualifying_opportunities = 0

    for summary in summaries:
        registry_total = max(registry_total, int(summary.get("registry_total", 0)))
        enabled_registry_count = max(enabled_registry_count, int(summary.get("enabled_sources", 0)))
        source_results_path = summary.get("source_results_path")
        if source_results_path and Path(source_results_path).exists():
            try:
                lines = Path(source_results_path).read_text(encoding="utf-8").splitlines()
            except Exception:
                lines = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not record.get("enabled", True):
                    continue
                if not record.get("attempted"):
                    continue
                identity = str(record.get("source_identity") or record.get("source_name") or "")
                if not identity:
                    continue
                attempted_sources.setdefault(identity, record)
                if record.get("success"):
                    successful_sources[identity] = record
                    failed_sources.pop(identity, None)
                elif identity not in successful_sources:
                    # Daily health is optimistic across repeated attempts:
                    # one legitimate success makes the identity successful for
                    # the day, and terminal buckets must stay disjoint.
                    failed_sources.setdefault(identity, record)
                qualifying_opportunities += int(record.get("qualifying_candidates") or 0)

    enabled_attempted_count = len(attempted_sources)
    disabled_sources = max(0, registry_total - enabled_registry_count)
    not_checked = max(0, enabled_registry_count - enabled_attempted_count)
    success_count = len(successful_sources)
    failed_count = len(failed_sources)
    if enabled_registry_count and enabled_attempted_count >= enabled_registry_count:
        status = "FULL"
    elif enabled_attempted_count > 0 or summaries:
        status = "PARTIAL"
    else:
        status = "FAILED"
    daily = {
        "date": date_value,
        "registry_total": registry_total,
        "enabled_registry_count": enabled_registry_count,
        "disabled_sources": disabled_sources,
        "unique_enabled_sources_attempted": enabled_attempted_count,
        "successful_sources": success_count,
        "failed_sources": failed_count,
        "not_checked": not_checked,
        "coverage_percentage": round((enabled_attempted_count / enabled_registry_count * 100.0) if enabled_registry_count else 100.0, 2),
        "qualifying_opportunities_found": qualifying_opportunities,
        "coverage_status": status,
        "run_count": len(summaries),
    }
    _safe_write_json(day_dir / "daily_coverage.json", daily)
    return daily


def latest_summary_path(runtime_root: Optional[str] = None) -> Path:
    base = Path(runtime_root).expanduser().resolve() if runtime_root else DEFAULT_RUNTIME_ROOT
    return base / "latest.json"


def load_latest_summary(runtime_root: Optional[str] = None) -> Dict[str, Any]:
    path = latest_summary_path(runtime_root)
    if not path.exists():
        raise FileNotFoundError("No latest source coverage summary found at %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_daily_summary(date_value: str, runtime_root: Optional[str] = None) -> Dict[str, Any]:
    base = Path(runtime_root).expanduser().resolve() if runtime_root else DEFAULT_RUNTIME_ROOT
    path = base / date_value / "daily_coverage.json"
    if not path.exists():
        raise FileNotFoundError("No daily source coverage summary found at %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def format_summary_lines(summary: Mapping[str, Any]) -> List[str]:
    not_checked = summary.get("not_checked")
    if not_checked is None:
        # Legacy per-run summaries predate ``not_checked``.  Derive it from
        # the coverage denominator instead of reusing skipped_sources, whose
        # normalised-record meaning is different.
        try:
            enabled = int(summary.get("enabled_sources", summary.get("enabled_registry_count", 0)) or 0)
            checked = int(summary.get("unique_sources_checked", summary.get("unique_enabled_sources_attempted", 0)) or 0)
            not_checked = max(0, enabled - checked)
        except (TypeError, ValueError):
            not_checked = 0
    return [
        "DATE %s" % (summary.get("date") or str(summary.get("completed_at", ""))[:10]),
        "REGISTRY TOTAL %s" % summary.get("registry_total", summary.get("enabled_registry_count", 0) + summary.get("not_checked", 0)),
        "ENABLED %s" % summary.get("enabled_sources", summary.get("enabled_registry_count", 0)),
        "DISABLED %s" % summary.get("disabled_sources", 0),
        "CHECKED %s" % summary.get("unique_sources_checked", summary.get("unique_enabled_sources_attempted", 0)),
        "SUCCESSFUL %s" % summary.get("successful_sources", 0),
        "FAILED %s" % summary.get("failed_sources", 0),
        "NOT CHECKED %s" % not_checked,
        "COVERAGE %% %s" % summary.get("coverage_percentage", 0),
        "QUALIFYING RFQs %s" % summary.get("qualifying_opportunities_found", 0),
        "STATUS %s" % summary.get("coverage_status", "UNKNOWN"),
    ]


def failure_records_from_summary(summary: Mapping[str, Any]) -> List[Dict[str, Any]]:
    result_path = summary.get("source_results_path")
    if not result_path:
        return []
    path = Path(str(result_path))
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("attempted") and not record.get("success"):
            records.append(record)
    return records


def attach_harvest_run_certificate_hooks() -> None:
    try:
        from app.services.rfq_lifecycle_service import RfqLifecycleService
    except Exception:
        return
    if getattr(RfqLifecycleService, "_source_coverage_certificate_hooked", False):
        return

    def _wrap(method_name: str) -> None:
        original = getattr(RfqLifecycleService, method_name, None)
        if original is None or getattr(original, "_source_coverage_certificate_wrapped", False):
            return

        def wrapped(self, *args: Any, **kwargs: Any):
            started_at = utc_now_iso()
            try:
                result = original(self, *args, **kwargs)
            except Exception as exc:
                completed_at = utc_now_iso()
                try:
                    write_run_certificate(
                        {
                            "started_at": started_at,
                            "completed_at": completed_at,
                            "execution_mode": method_name,
                            "full_sweep_requested": False,
                            "complete": False,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
                except Exception as cert_exc:  # pragma: no cover - defensive logging only
                    LOGGER.warning("source coverage failed-run certificate emission failed for %s: %s", method_name, cert_exc)
                raise
            if isinstance(result, Mapping):
                try:
                    payload = dict(result)
                    payload["started_at"] = started_at
                    payload["completed_at"] = utc_now_iso()
                    write_run_certificate(payload)
                except Exception as exc:  # pragma: no cover - defensive logging only
                    LOGGER.warning("source coverage certificate emission failed for %s: %s", method_name, exc)
            return result

        wrapped._source_coverage_certificate_wrapped = True  # type: ignore[attr-defined]
        setattr(RfqLifecycleService, method_name, wrapped)

    for method_name in (
        "ingest_discovered",
        "run_discovery_cycle",
        "run_golden_cycle",
        "run_live_pilot",
    ):
        _wrap(method_name)

    RfqLifecycleService._source_coverage_certificate_hooked = True  # type: ignore[attr-defined]
