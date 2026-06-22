from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime_paths import get_runtime_paths
from app.services.harvest_source_registry_service import CURATED_LIVE_SOURCE_FILE, load_harvest_sources
from app.services import tender_harvester


FAILURE_TYPES = {
    "dns_failed",
    "timeout",
    "http_error",
    "parse_error",
    "no_candidates",
    "duplicate_url",
    "unknown_error",
}


@dataclass(frozen=True)
class AttemptResult:
    source_name: str
    category: str
    url: str
    attempted: bool
    reachable: bool
    status: str
    failure_type: str
    investigation_marker: str
    rfqs_found: int
    qualified_rfqs: int
    submission_candidates: int
    elapsed_seconds: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "category": self.category,
            "url": self.url,
            "attempted": self.attempted,
            "reachable": self.reachable,
            "status": self.status,
            "failure_type": self.failure_type,
            "investigation_marker": self.investigation_marker,
            "rfqs_found": self.rfqs_found,
            "qualified_rfqs": self.qualified_rfqs,
            "submission_candidates": self.submission_candidates,
            "elapsed_seconds": round(float(self.elapsed_seconds or 0.0), 3),
        }


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    text = _clean(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_url(url: Any) -> str:
    text = _clean(url).lower()
    if not text:
        return ""
    return text.rstrip("/")


def _normalize_name(source: Dict[str, Any]) -> str:
    return _clean(source.get("name") or source.get("source_name") or source.get("portal_name"))


def _detect_registry_paths() -> List[Path]:
    runtime_paths = get_runtime_paths()
    project_root = runtime_paths.project_root
    runtime_root = runtime_paths.runtime_root
    env_paths = [
        _clean(os.getenv("LMCP_HARVEST_SOURCE_REGISTRY_PATH")),
        _clean(os.getenv("HARVEST_SOURCE_REGISTRY_PATH")),
        _clean(os.getenv("LMCP_SOURCE_REGISTRY_PATH")),
    ]
    candidates = [Path(value).expanduser() for value in env_paths if value]
    candidates.extend(
        [
            project_root / "app" / "data" / "harvest_sources.json",
            project_root / "app" / "data" / "smoke_harvest_sources.json",
            runtime_root / "manual_production" / "harvest_sources.json",
            runtime_root / "manual_production" / "harvest_sources.jsonl",
        ]
    )
    return candidates


def load_registry_sources() -> List[Dict[str, Any]]:
    for path in _detect_registry_paths():
        if not path.exists():
            continue
        try:
            return load_harvest_sources(path)
        except Exception:
            continue
    try:
        return load_harvest_sources(CURATED_LIVE_SOURCE_FILE)
    except Exception:
        return []


def _load_source_health_snapshot() -> Dict[str, Dict[str, Any]]:
    snapshot: Dict[str, Dict[str, Any]] = {}
    runtime_paths = get_runtime_paths()
    for path in [
        runtime_paths.runtime_root / "source_health.json",
        runtime_paths.manual_production_dir / "harvest_source_health.jsonl",
    ]:
        if not path.exists():
            continue
        try:
            if path.suffix.lower() == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    for key, value in payload.items():
                        if isinstance(value, dict):
                            snapshot[_normalize_url(key) or _clean(key).lower()] = value
                            name = _clean(value.get("source_name") or value.get("name"))
                            url = _normalize_url(value.get("source_url"))
                            if name:
                                snapshot[name.lower()] = value
                            if url:
                                snapshot[url] = value
            else:
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        continue
                    for key in ("source_id", "source_name", "name", "source_url"):
                        text = _clean(payload.get(key))
                        if text:
                            snapshot[text.lower()] = payload
        except Exception:
            continue
    return snapshot


def _lookup_source_health(source: Dict[str, Any], snapshot: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    candidates = [
        _normalize_name(source).lower(),
        _normalize_url(source.get("url")),
        _normalize_url(source.get("list_url")),
    ]
    for key in candidates:
        if key and key in snapshot:
            return snapshot[key]
    return {}


def _health_counts_from_row(row: Dict[str, Any]) -> Tuple[int, int, int]:
    rfqs_found = int(row.get("candidate_total") or 0)
    qualified = int(row.get("qualified_candidate_total") or 0)
    submission_candidates = int(row.get("document_candidate_total") or 0)
    return rfqs_found, qualified, submission_candidates


def _classify_attempt_failure(
    *,
    preflight_status: str,
    error_message: str,
    source_health_row: Dict[str, Any],
    attempted: bool,
) -> str:
    if not attempted:
        return "duplicate_url"

    lower = _clean(error_message).lower()
    health_status = _clean(source_health_row.get("health_status")).lower()
    acquisition_status = _clean(source_health_row.get("acquisition_status")).lower()
    last_status = _clean(source_health_row.get("last_status")).lower()

    if preflight_status == "dns_failed" or any(term in lower for term in ("nameresolutionerror", "dns", "resolve", "nodename")):
        return "dns_failed"
    if preflight_status == "timeout" or "timeout" in lower or "timed out" in lower:
        return "timeout"
    if preflight_status in {"http_failed", "http_error"}:
        return "http_error"
    if any(term in lower for term in ("parse", "xml", "json", "html parse")):
        return "parse_error"
    if acquisition_status == "no_candidates" or last_status == "ok_empty" or health_status in {"empty", "degraded"} and int(source_health_row.get("candidate_total") or 0) == 0:
        return "no_candidates"
    if acquisition_status == "parse_failed":
        return "parse_error"
    if acquisition_status == "http_failed":
        return "http_error"
    if acquisition_status == "dns_failed":
        return "dns_failed"
    return "unknown_error"


def _preflight_source(source: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    return tender_harvester._preflight_source_acquisition(source, timeout_seconds=timeout)  # noqa: SLF001


def _curl_head_probe(source: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    source_url = _clean(source.get("url") or source.get("list_url"))
    if not source_url:
        return {
            "status": "skipped",
            "reachable": False,
            "http_status_code": 0,
            "http_status": 0,
            "error_message": "missing_source_url",
        }
    try:
        curl_command = " ".join(
            [
                "curl",
                "-sS",
                "-I",
                "-L",
                "--max-time",
                str(max(1, int(timeout))),
                shlex.quote(source_url),
            ]
        )
        completed = subprocess.run(
            ["/bin/zsh", "-lc", curl_command],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return {
            "status": "unknown",
            "reachable": False,
            "http_status_code": 0,
            "http_status": 0,
            "error_message": str(exc),
        }

    combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    http_status_code = 0
    for line in combined.splitlines():
        text = line.strip()
        if text.upper().startswith("HTTP/"):
            parts = text.split()
            for part in parts[1:]:
                if part.isdigit():
                    http_status_code = int(part)
                    break
            if http_status_code:
                break
    reachable = http_status_code in {200, 201, 202, 203, 204, 206, 301, 302, 303, 307, 308, 401, 403, 405}
    if completed.returncode == 0 and reachable:
        return {
            "status": "ok",
            "reachable": True,
            "http_status_code": http_status_code,
            "http_status": http_status_code,
            "error_message": "",
            "fallback_used": True,
        }
    if completed.returncode != 0 and "Could not resolve host" in combined:
        return {
            "status": "dns_failed",
            "reachable": False,
            "http_status_code": http_status_code,
            "http_status": http_status_code,
            "error_message": combined.strip()[:240],
            "fallback_used": True,
        }
    if completed.returncode != 0 and "timed out" in combined.lower():
        return {
            "status": "timeout",
            "reachable": False,
            "http_status_code": http_status_code,
            "http_status": http_status_code,
            "error_message": combined.strip()[:240],
            "fallback_used": True,
        }
    return {
        "status": "http_failed" if http_status_code else "unknown",
        "reachable": reachable,
        "http_status_code": http_status_code,
        "http_status": http_status_code,
        "error_message": combined.strip()[:240],
        "fallback_used": True,
    }


def _preflight_source_with_fallback(source: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    primary = _preflight_source(source, timeout)
    if _clean(primary.get("status")).lower() != "dns_failed":
        primary.setdefault("dns_runtime_suspected", False)
        return primary
    fallback = _curl_head_probe(source, timeout)
    if fallback.get("reachable") and _clean(fallback.get("status")).lower() == "ok":
        merged = dict(primary)
        merged.update(fallback)
        merged["status"] = "ok"
        merged["reachable"] = True
        merged["dns_resolved"] = True
        merged["dns_status"] = "fallback_ok"
        merged["dns_runtime_suspected"] = True
        return merged
    if fallback:
        fallback.setdefault("dns_runtime_suspected", True)
        return fallback
    primary["dns_runtime_suspected"] = True
    return primary


def _attempt_one(
    source: Dict[str, Any],
    *,
    timeout: int,
    source_health_snapshot: Dict[str, Dict[str, Any]],
) -> AttemptResult:
    started = time.perf_counter()
    preflight = {}
    try:
        preflight = _preflight_source_with_fallback(source, timeout)
        status = _clean(preflight.get("status")) or "unknown"
        reachable = bool(preflight.get("reachable"))
        investigation_marker = "dns_runtime_suspected" if bool(preflight.get("dns_runtime_suspected")) else ""
        source_health_row = _lookup_source_health(source, source_health_snapshot)
        rfqs_found, qualified, submission_candidates = _health_counts_from_row(source_health_row)
        if status == "ok" and rfqs_found == 0 and qualified == 0 and submission_candidates == 0:
            failure_type = "no_candidates"
            status = "no_candidates"
        elif status == "ok":
            failure_type = "unknown_error" if not reachable else "no_candidates" if rfqs_found == 0 else "unknown_error"
        else:
            failure_type = _classify_attempt_failure(
                preflight_status=status,
                error_message=_clean(preflight.get("error_message")),
                source_health_row=source_health_row,
                attempted=True,
            )
        return AttemptResult(
            source_name=_normalize_name(source),
            category=_clean(source.get("category") or source.get("source_group") or source.get("category_group")),
            url=_clean(source.get("url") or source.get("list_url")),
            attempted=True,
            reachable=reachable,
            status=status,
            failure_type=failure_type,
            investigation_marker=investigation_marker,
            rfqs_found=rfqs_found,
            qualified_rfqs=qualified,
            submission_candidates=submission_candidates,
            elapsed_seconds=time.perf_counter() - started,
        )
    except Exception as exc:
        source_health_row = _lookup_source_health(source, source_health_snapshot)
        rfqs_found, qualified, submission_candidates = _health_counts_from_row(source_health_row)
        return AttemptResult(
            source_name=_normalize_name(source),
            category=_clean(source.get("category") or source.get("source_group") or source.get("category_group")),
            url=_clean(source.get("url") or source.get("list_url")),
            attempted=True,
            reachable=False,
            status="failed",
            failure_type=_classify_attempt_failure(
                preflight_status="unknown",
                error_message=str(exc),
                source_health_row=source_health_row,
                attempted=True,
            ),
            investigation_marker="",
            rfqs_found=rfqs_found,
            qualified_rfqs=qualified,
            submission_candidates=submission_candidates,
            elapsed_seconds=time.perf_counter() - started,
        )


def _prepare_attempt_sources(
    sources: Sequence[Dict[str, Any]],
    limit: int,
) -> Tuple[List[Dict[str, Any]], List[AttemptResult]]:
    selected: List[Dict[str, Any]] = []
    duplicates: List[AttemptResult] = []
    seen_urls = set()

    for source in sources:
        if not isinstance(source, dict):
            continue
        if not _as_bool(source.get("enabled", True)):
            continue
        url = _normalize_url(source.get("url") or source.get("list_url"))
        if not url:
            continue
        if url in seen_urls:
            duplicates.append(
                AttemptResult(
                    source_name=_normalize_name(source),
                    category=_clean(source.get("category") or source.get("source_group") or source.get("category_group")),
                    url=_clean(source.get("url") or source.get("list_url")),
                    attempted=False,
                    reachable=False,
                    status="skipped",
                    failure_type="duplicate_url",
                    investigation_marker="",
                    rfqs_found=0,
                    qualified_rfqs=0,
                    submission_candidates=0,
                    elapsed_seconds=0.0,
                )
            )
            continue
        seen_urls.add(url)
        selected.append(source)
        if len(selected) >= limit:
            break

    return selected, duplicates


def _build_leaderboard(results: Sequence[AttemptResult], limit: int = 20) -> List[Dict[str, Any]]:
    leaderboard: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for result in results:
        if not result.attempted:
            continue
        key = (result.source_name.lower(), result.category.lower(), result.url.lower())
        bucket = leaderboard.setdefault(
            key,
            {
                "source_name": result.source_name,
                "category": result.category,
                "url": result.url,
                "rfqs_produced": 0,
                "qualified_rfqs_produced": 0,
                "submission_candidates_produced": 0,
                "attempts": 0,
                "reachable_attempts": 0,
                "failure_types": Counter(),
            },
        )
        bucket["attempts"] += 1
        if result.reachable:
            bucket["reachable_attempts"] += 1
        bucket["rfqs_produced"] += int(result.rfqs_found)
        bucket["qualified_rfqs_produced"] += int(result.qualified_rfqs)
        bucket["submission_candidates_produced"] += int(result.submission_candidates)
        bucket["failure_types"][result.failure_type] += 1

    rows = list(leaderboard.values())
    rows.sort(
        key=lambda row: (
            -int(row["rfqs_produced"]),
            -int(row["qualified_rfqs_produced"]),
            -int(row["submission_candidates_produced"]),
            row["source_name"].lower(),
        )
    )
    for row in rows:
        row["failure_types"] = dict(row["failure_types"])
    return rows[: max(1, limit)]


def _build_metrics(
    results: Sequence[AttemptResult],
    *,
    configured_sources: int,
    enabled_sources: int,
    unique_urls: int,
) -> Dict[str, Any]:
    attempted = [row for row in results if row.attempted]
    reachable = [row for row in attempted if row.reachable]
    rfq_producing = [row for row in attempted if row.rfqs_found > 0]
    qualified = [row for row in attempted if row.qualified_rfqs > 0]
    submission_candidates = [row for row in attempted if row.submission_candidates > 0]
    dns_runtime_suspected = [row for row in attempted if row.failure_type == "no_candidates" and row.investigation_marker == "dns_runtime_suspected"]
    failure_counts = Counter(row.failure_type for row in results)

    attempted_count = len(attempted)
    return {
        "configured_sources": configured_sources,
        "enabled_sources": enabled_sources,
        "unique_urls": unique_urls,
        "attempted_sources": attempted_count,
        "reachable_sources": len(reachable),
        "rfq_producing_sources": len(rfq_producing),
        "qualified_rfq_sources": len(qualified),
        "submission_candidate_sources": len(submission_candidates),
        "dns_runtime_suspected_sources": len(dns_runtime_suspected),
        "harvest_coverage_percent": round((attempted_count / max(configured_sources, 1)) * 100.0, 2),
        "rfq_producing_source_percent": round((len(rfq_producing) / max(attempted_count, 1)) * 100.0, 2),
        "top_failure_types": failure_counts.most_common(),
    }


def _append_summary_doc(summary_path: Path, *, metrics: Dict[str, Any], leaderboard: Sequence[Dict[str, Any]], results: Sequence[AttemptResult]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"## Harvest Effectiveness Run - { _now_iso() }")
    lines.append("")
    lines.append("### Coverage Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for key in [
        "configured_sources",
        "enabled_sources",
        "unique_urls",
        "attempted_sources",
        "reachable_sources",
        "rfq_producing_sources",
        "qualified_rfq_sources",
        "submission_candidate_sources",
        "dns_runtime_suspected_sources",
        "harvest_coverage_percent",
        "rfq_producing_source_percent",
    ]:
        lines.append(f"| {key} | {metrics[key]} |")
    lines.append("")
    lines.append("### Top Failure Types")
    lines.append("")
    for failure_type, count in metrics["top_failure_types"]:
        lines.append(f"- {failure_type}: {count}")
    lines.append("")
    lines.append("### Top Producers")
    lines.append("")
    lines.append("| Source | RFQs | Qualified | Submission Candidates |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in leaderboard[:10]:
        lines.append(
            f"| {row['source_name']} | {row['rfqs_produced']} | {row['qualified_rfqs_produced']} | {row['submission_candidates_produced']} |"
        )
    lines.append("")
    lines.append("### Attempted Sources")
    lines.append("")
    lines.append("| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: |")
    for row in results[: min(len(results), 40)]:
        lines.append(
            f"| {row.source_name} | {row.status} | {row.failure_type} | {row.investigation_marker or ''} | {row.rfqs_found} | {row.qualified_rfqs} | {row.submission_candidates} |"
        )
    lines.append("")
    with summary_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _build_summary_lines(
    *,
    metrics: Dict[str, Any],
    leaderboard: Sequence[Dict[str, Any]],
    results: Sequence[AttemptResult],
) -> List[str]:
    lines = [
        "# Sprint 7 Harvest Effectiveness Summary",
        "",
        f"Generated at: {_now_iso()}",
        "",
        "## Coverage Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in [
        "configured_sources",
        "enabled_sources",
        "unique_urls",
        "attempted_sources",
        "reachable_sources",
        "rfq_producing_sources",
        "qualified_rfq_sources",
        "submission_candidate_sources",
        "dns_runtime_suspected_sources",
        "harvest_coverage_percent",
        "rfq_producing_source_percent",
    ]:
        lines.append(f"| {key} | {metrics[key]} |")
    lines.extend(["", "## Top Failure Types", ""])
    for failure_type, count in metrics["top_failure_types"]:
        lines.append(f"- {failure_type}: {count}")
    lines.extend(["", "## Top Producers", "", "| Source | RFQs | Qualified | Submission Candidates |", "| --- | ---: | ---: | ---: |"])
    for row in leaderboard[:10]:
        lines.append(
            f"| {row['source_name']} | {row['rfqs_produced']} | {row['qualified_rfqs_produced']} | {row['submission_candidates_produced']} |"
        )
    lines.extend(["", "## Attempted Sources", "", "| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |", "| --- | --- | --- | --- | ---: | ---: | ---: |"])
    for row in results[: min(len(results), 40)]:
        lines.append(
            f"| {row.source_name} | {row.status} | {row.failure_type} | {row.investigation_marker or ''} | {row.rfqs_found} | {row.qualified_rfqs} | {row.submission_candidates} |"
        )
    lines.append("")
    return lines


def run_harvest_effectiveness(
    *,
    limit: int = 200,
    timeout: int = 20,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
    sources: Optional[Sequence[Dict[str, Any]]] = None,
    source_health_snapshot: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    registry_sources = list(sources) if sources is not None else load_registry_sources()
    enabled_sources = [source for source in registry_sources if _as_bool(source.get("enabled", True))]
    unique_urls = len(
        {
            _normalize_url(source.get("url") or source.get("list_url"))
            for source in enabled_sources
            if _normalize_url(source.get("url") or source.get("list_url"))
        }
    )

    attempt_sources, duplicate_rows = _prepare_attempt_sources(enabled_sources, limit=max(1, limit))
    source_health_snapshot = source_health_snapshot if isinstance(source_health_snapshot, dict) else _load_source_health_snapshot()

    results: List[AttemptResult] = []
    if attempt_sources:
        max_workers = min(20, max(1, len(attempt_sources)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_attempt_one, source, timeout=timeout, source_health_snapshot=source_health_snapshot): idx
                for idx, source in enumerate(attempt_sources)
            }
            ordered: Dict[int, AttemptResult] = {}
            for future in as_completed(future_map):
                idx = future_map[future]
                ordered[idx] = future.result()
            results.extend(ordered[idx] for idx in sorted(ordered))

    results.extend(duplicate_rows)

    metrics = _build_metrics(
        results,
        configured_sources=len(registry_sources),
        enabled_sources=len(enabled_sources),
        unique_urls=unique_urls,
    )
    leaderboard = _build_leaderboard(results, limit=20)

    output_root = Path(output_dir) if output_dir else get_runtime_paths().runtime_root / "harvest_effectiveness"
    output_root.mkdir(parents=True, exist_ok=True)

    coverage_path = output_root / "harvest_coverage_metrics.json"
    attempts_path = output_root / "source_attempt_results.json"
    leaderboard_path = output_root / "source_productivity_leaderboard.json"
    summary_path = output_root / "harvest_effectiveness_summary.md"

    coverage_payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "metrics": metrics,
    }
    attempts_payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "count": len(results),
        "results": [row.as_dict() for row in results],
    }
    leaderboard_payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "count": len(leaderboard),
        "leaderboard": leaderboard,
    }

    coverage_path.write_text(json.dumps(coverage_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    attempts_path.write_text(json.dumps(attempts_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    leaderboard_path.write_text(json.dumps(leaderboard_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    summary_path.write_text(
        "\n".join(_build_summary_lines(metrics=metrics, leaderboard=leaderboard, results=results)),
        encoding="utf-8",
    )

    if not dry_run:
        docs_path = get_runtime_paths().project_root / "docs" / "operations_validation_pack" / "sprint_7_harvest_coverage_audit.md"
        _append_summary_doc(docs_path, metrics=metrics, leaderboard=leaderboard, results=results)

    return {
        "coverage": coverage_payload,
        "attempts": attempts_payload,
        "leaderboard": leaderboard_payload,
        "output_dir": str(output_root),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sprint 7 Harvest Effectiveness command")
    parser.add_argument("--limit", type=int, default=200, help="Maximum number of unique enabled sources to attempt")
    parser.add_argument("--timeout", type=int, default=20, help="Per-source preflight timeout in seconds")
    parser.add_argument("--output-dir", type=str, default="runtime/harvest_effectiveness", help="Output directory for audit reports")
    parser.add_argument("--dry-run", action="store_true", help="Write machine-readable reports but skip doc append")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_harvest_effectiveness(
        limit=max(1, int(args.limit or 200)),
        timeout=max(1, int(args.timeout or 20)),
        output_dir=Path(args.output_dir),
        dry_run=bool(args.dry_run),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
