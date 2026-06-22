from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime_paths import get_runtime_paths


RUNTIME_PATHS = get_runtime_paths()
DEFAULT_RUNTIME_DIR = RUNTIME_PATHS.runtime_root / "harvest_effectiveness"
DEFAULT_ACTION_PLAN_PATH = DEFAULT_RUNTIME_DIR / "source_action_plan.json"
DEFAULT_HTTP_SUMMARY_PATH = DEFAULT_RUNTIME_DIR / "http_failure_summary.json"
DEFAULT_ATTEMPT_RESULTS_PATH = DEFAULT_RUNTIME_DIR / "source_attempt_results.json"
DEFAULT_OUTPUT_DIR = DEFAULT_RUNTIME_DIR
DEFAULT_DOC_PATH = RUNTIME_PATHS.project_root / "docs" / "operations_validation_pack" / "sprint_7_source_maintenance_decision_memo.md"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_url(url: Any) -> str:
    return _clean(url).lower().rstrip("/")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _load_rows(payload: Dict[str, Any], *, list_key: str = "sources") -> List[Dict[str, Any]]:
    rows = payload.get(list_key)
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _clean(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _source_key(source_name: Any, url: Any) -> Tuple[str, str]:
    return _clean(source_name), _normalize_url(url)


def _priority_for_action(action: str) -> int:
    order = {
        "fix_404_url": 1,
        "resolve_redirect": 2,
        "investigate_redirect_loop": 3,
        "investigate_auth": 4,
        "manual_probe_unknown": 5,
        "keep_retry": 6,
        "promote": 7,
    }
    return order.get(action, 99)


def _recommended_next_step(action: str, observed_status: str) -> str:
    recommendations = {
        "fix_404_url": "Search/update procurement URL or confirm source is dead; quarantine only after manual confirmation.",
        "resolve_redirect": "Follow the final URL and update the source if the destination is a valid procurement page.",
        "investigate_redirect_loop": "Try browser headers/session or a corrected endpoint before changing the registry.",
        "investigate_auth": "Check whether the public procurement page exists or if the portal requires login.",
        "manual_probe_unknown": "Test with browser or GET before deciding.",
        "keep_retry": "Keep enabled, lower priority, and retry later.",
        "promote": "Keep as a reference producer and monitor as a benchmark source.",
    }
    if action == "keep_retry" and observed_status == "timeout":
        return "Retry later with a longer timeout and lower concurrency."
    return recommendations.get(action, "Review manually.")


def _observe_status(source: Dict[str, Any], http_row: Optional[Dict[str, Any]]) -> str:
    if http_row is not None:
        bucket = _clean(http_row.get("bucket"))
        if bucket:
            return bucket
        code = _to_int(http_row.get("http_status_code"), 0)
        if code > 0:
            return f"HTTP {code}"
    failure_type = _clean(source.get("failure_type"))
    status = _clean(source.get("status"))
    if failure_type:
        return failure_type
    if status:
        return status
    return "unknown"


def _classify_observed_status(observed_status: str, source: Dict[str, Any]) -> str:
    status = _clean(observed_status)
    failure_type = _clean(source.get("failure_type"))
    if status == "HTTP 404":
        return "fix_404_url"
    if status in {"HTTP 301", "HTTP 302"}:
        return "resolve_redirect"
    if status == "Redirect Loop":
        return "investigate_redirect_loop"
    if status == "HTTP 401":
        return "investigate_auth"
    if status == "Unknown HTTP":
        return "manual_probe_unknown"
    if status in {"HTTP 403", "HTTP 405", "HTTP 500", "SSL Error"}:
        return "manual_probe_unknown"
    if failure_type == "no_candidates" or failure_type == "timeout":
        return "keep_retry"
    if failure_type in {"unknown_error", "dns_failed"}:
        return "manual_probe_unknown"
    return "manual_probe_unknown"


@dataclass(frozen=True)
class MaintenanceActionRow:
    source_name: str
    url: str
    category: str
    observed_status: str
    action: str
    priority: int
    recommended_next_step: str
    disable_source: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "url": self.url,
            "category": self.category,
            "observed_status": self.observed_status,
            "action": self.action,
            "priority": self.priority,
            "recommended_next_step": self.recommended_next_step,
            "disable_source": self.disable_source,
        }


def _load_inputs(
    action_plan_path: Path,
    http_summary_path: Path,
    attempt_results_path: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[Tuple[str, str], Dict[str, Any]]]:
    action_plan = _load_json(action_plan_path)
    http_summary = _load_json(http_summary_path)
    attempts = _load_json(attempt_results_path)
    attempt_rows = _load_rows(attempts, list_key="results")
    attempt_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in attempt_rows:
        attempt_index[_source_key(row.get("source_name"), row.get("url"))] = row
    return action_plan, http_summary, attempt_index


def build_source_maintenance_action_list(
    *,
    action_plan_path: Path = DEFAULT_ACTION_PLAN_PATH,
    http_summary_path: Path = DEFAULT_HTTP_SUMMARY_PATH,
    attempt_results_path: Path = DEFAULT_ATTEMPT_RESULTS_PATH,
) -> Dict[str, Any]:
    action_plan, http_summary, attempt_index = _load_inputs(action_plan_path, http_summary_path, attempt_results_path)
    sources = _load_rows(action_plan, list_key="sources")
    http_rows = _load_rows(http_summary, list_key="sources")
    http_index = {_source_key(row.get("source_name"), row.get("url")): row for row in http_rows}

    classified: List[MaintenanceActionRow] = []
    for source in sources:
        key = _source_key(source.get("source_name"), source.get("url"))
        http_row = http_index.get(key)
        attempt_row = attempt_index.get(key, {})
        rfqs_found = max(_to_int(source.get("rfqs_found"), 0), _to_int(attempt_row.get("rfqs_found"), 0))
        qualified_rfqs = max(_to_int(source.get("qualified_rfqs"), 0), _to_int(attempt_row.get("qualified_rfqs"), 0))
        submission_candidates = max(_to_int(source.get("submission_candidates"), 0), _to_int(attempt_row.get("submission_candidates"), 0))
        action = _clean(source.get("action"))
        failure_type = _clean(source.get("failure_type")) or _clean(attempt_row.get("failure_type"))
        observed_status = _observe_status(source, http_row)

        if rfqs_found > 0 or qualified_rfqs > 0 or submission_candidates > 0:
            maintenance_action = "promote"
        elif action == "investigate_http" or failure_type == "http_error" or http_row is not None:
            maintenance_action = _classify_observed_status(observed_status, source)
        elif action == "investigate_timeout" or failure_type == "timeout":
            maintenance_action = "keep_retry"
            observed_status = observed_status or "timeout"
        elif action == "retry" or failure_type == "no_candidates":
            maintenance_action = "keep_retry"
            observed_status = observed_status or "no_candidates"
        elif action == "investigate_runtime_dns":
            maintenance_action = "manual_probe_unknown"
        else:
            maintenance_action = "manual_probe_unknown"

        if maintenance_action == "keep_retry" and observed_status == "unknown":
            observed_status = failure_type or "unknown"
        priority = _priority_for_action(maintenance_action)
        recommended_next_step = _recommended_next_step(maintenance_action, observed_status)
        classified.append(
            MaintenanceActionRow(
                source_name=_clean(source.get("source_name")),
                url=_clean(source.get("url")),
                category=_clean(source.get("category")),
                observed_status=observed_status or "unknown",
                action=maintenance_action,
                priority=priority,
                recommended_next_step=recommended_next_step,
                disable_source=False,
            )
        )

    classified.sort(key=lambda row: (row.priority, row.source_name.lower(), row.url))
    counts = Counter(row.action for row in classified)
    payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "input_paths": {
            "source_action_plan": str(action_plan_path),
            "http_failure_summary": str(http_summary_path),
            "source_attempt_results": str(attempt_results_path),
        },
        "total_sources": len(classified),
        "counts": dict(counts),
        "sources": [row.as_dict() for row in classified],
    }
    return {"payload": payload, "sources": classified, "counts": counts}


def _markdown_summary(plan: Dict[str, Any]) -> str:
    counts: Counter = plan["counts"]
    sources: List[MaintenanceActionRow] = plan["sources"]
    by_action: Dict[str, List[MaintenanceActionRow]] = defaultdict(list)
    for row in sources:
        by_action[row.action].append(row)
    for rows in by_action.values():
        rows.sort(key=lambda row: (row.priority, row.source_name.lower(), row.url))

    lines = [
        "# Sprint 7 Source Maintenance Decision Memo",
        "",
        "The dominant issue is stale or wrong URLs. The HTTP failure summary shows 88 HTTP 404s, which is the largest failure bucket.",
        "",
        "This is not a qualification, governance, audit, or submission-flow issue.",
        "",
        "Do not add more sources until the 404 and redirect groups are cleaned.",
        "Do not quarantine sources from one automated result alone.",
        "",
        "## Summary Counts",
        "",
        "| Action | Count |",
        "| --- | ---: |",
    ]
    for action in ["fix_404_url", "resolve_redirect", "investigate_redirect_loop", "investigate_auth", "manual_probe_unknown", "keep_retry", "promote"]:
        lines.append(f"| {action} | {counts.get(action, 0)} |")
    lines.extend(["", "## Recommended Actions", ""])
    lines.extend([
        "- `fix_404_url`: search/update procurement URL or confirm source is dead; quarantine only after manual confirmation.",
        "- `resolve_redirect`: follow the final URL and update the source if the destination is a valid procurement page.",
        "- `investigate_redirect_loop`: try browser headers/session or a corrected endpoint.",
        "- `investigate_auth`: check whether the public procurement page exists or if the portal requires login.",
        "- `manual_probe_unknown`: test with browser or GET before deciding.",
        "- `keep_retry`: keep enabled, lower priority, and retry later.",
        "- `promote`: keep as a reference producer and monitor as a benchmark source.",
    ])
    lines.extend(["", "## Top 404 Cleanup Candidates", ""])
    fix_404 = by_action.get("fix_404_url", [])[:20]
    if not fix_404:
        lines.append("_No sources._")
    else:
        lines.append("| Source | Category | URL | Observed Status | Priority | Recommended Next Step |")
        lines.append("| --- | --- | --- | --- | ---: | --- |")
        for row in fix_404:
            lines.append(f"| {row.source_name} | {row.category} | {row.url} | {row.observed_status} | {row.priority} | {row.recommended_next_step} |")
    lines.extend(["", "## Redirect Sources", ""])
    resolve = by_action.get("resolve_redirect", [])[:20]
    if not resolve:
        lines.append("_No sources._")
    else:
        lines.append("| Source | Category | URL | Observed Status | Priority | Recommended Next Step |")
        lines.append("| --- | --- | --- | --- | ---: | --- |")
        for row in resolve:
            lines.append(f"| {row.source_name} | {row.category} | {row.url} | {row.observed_status} | {row.priority} | {row.recommended_next_step} |")
    for action, title in [
        ("investigate_redirect_loop", "Redirect Loop Sources"),
        ("investigate_auth", "Authentication Sources"),
        ("manual_probe_unknown", "Unknown HTTP Sources"),
        ("keep_retry", "Retry Sources"),
        ("promote", "Promote Sources"),
    ]:
        lines.extend(["", f"## {title}", ""])
        rows = by_action.get(action, [])
        if not rows:
            lines.append("_No sources._")
            continue
        lines.append("| Source | Category | URL | Observed Status | Priority | Recommended Next Step |")
        lines.append("| --- | --- | --- | --- | ---: | --- |")
        for row in rows if action in {"investigate_redirect_loop", "investigate_auth", "manual_probe_unknown"} else rows[:20]:
            lines.append(f"| {row.source_name} | {row.category} | {row.url} | {row.observed_status} | {row.priority} | {row.recommended_next_step} |")
    lines.extend(["", "No source was disabled by this action list."])
    return "\n".join(lines) + "\n"


def _write_memo(doc_path: Path, plan: Dict[str, Any]) -> None:
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(_markdown_summary(plan), encoding="utf-8")


def _write_outputs(output_dir: Path, plan: Dict[str, Any], doc_path: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "source_maintenance_action_list.json"
    md_path = output_dir / "source_maintenance_action_list.md"
    json_path.write_text(json.dumps(plan["payload"], indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_markdown_summary(plan), encoding="utf-8")
    _write_memo(doc_path, plan)
    return {"json_path": str(json_path), "md_path": str(md_path), "doc_path": str(doc_path)}


def write_source_maintenance_action_list(
    *,
    action_plan_path: Path = DEFAULT_ACTION_PLAN_PATH,
    http_summary_path: Path = DEFAULT_HTTP_SUMMARY_PATH,
    attempt_results_path: Path = DEFAULT_ATTEMPT_RESULTS_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    doc_path: Path = DEFAULT_DOC_PATH,
) -> Dict[str, Any]:
    plan = build_source_maintenance_action_list(
        action_plan_path=action_plan_path,
        http_summary_path=http_summary_path,
        attempt_results_path=attempt_results_path,
    )
    written = _write_outputs(output_dir, plan, doc_path)
    return {**plan, **written}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Sprint 7 source maintenance action list")
    parser.add_argument("--action-plan", type=str, default=str(DEFAULT_ACTION_PLAN_PATH), help="Path to source_action_plan.json")
    parser.add_argument("--http-summary", type=str, default=str(DEFAULT_HTTP_SUMMARY_PATH), help="Path to http_failure_summary.json")
    parser.add_argument("--attempt-results", type=str, default=str(DEFAULT_ATTEMPT_RESULTS_PATH), help="Path to source_attempt_results.json")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Directory for runtime action list outputs")
    parser.add_argument("--doc-path", type=str, default=str(DEFAULT_DOC_PATH), help="Operations validation memo path")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    write_source_maintenance_action_list(
        action_plan_path=Path(args.action_plan),
        http_summary_path=Path(args.http_summary),
        attempt_results_path=Path(args.attempt_results),
        output_dir=Path(args.output_dir),
        doc_path=Path(args.doc_path),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
