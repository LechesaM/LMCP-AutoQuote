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


DEFAULT_INPUT_PATH = get_runtime_paths().runtime_root / "harvest_effectiveness" / "source_attempt_results.json"
DEFAULT_OUTPUT_DIR = get_runtime_paths().runtime_root / "harvest_effectiveness"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_url(url: Any) -> str:
    text = _clean(url).lower()
    return text.rstrip("/")


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SourceAction:
    source_name: str
    category: str
    url: str
    action: str
    reason: str
    failure_type: str
    status: str
    reachable: bool
    rfqs_found: int
    qualified_rfqs: int
    submission_candidates: int
    http_status_code: Optional[int]
    investigation_marker: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "category": self.category,
            "url": self.url,
            "action": self.action,
            "reason": self.reason,
            "failure_type": self.failure_type,
            "status": self.status,
            "reachable": self.reachable,
            "rfqs_found": self.rfqs_found,
            "qualified_rfqs": self.qualified_rfqs,
            "submission_candidates": self.submission_candidates,
            "http_status_code": self.http_status_code,
            "investigation_marker": self.investigation_marker,
        }


def _load_attempt_results(path: Path = DEFAULT_INPUT_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        rows = payload["results"]
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _source_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return _clean(row.get("source_name")), _normalize_url(row.get("url"))


def _aggregate_source_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_source_key(row)].append(row)

    aggregated: List[Dict[str, Any]] = []
    for (source_name, url), entries in grouped.items():
        first = entries[0]
        aggregated.append(
            {
                "source_name": source_name,
                "category": _clean(first.get("category")),
                "url": url or _clean(first.get("url")),
                "entries": entries,
            }
        )
    aggregated.sort(key=lambda row: (row["source_name"].lower(), row["url"]))
    return aggregated


def classify_source(rows: Sequence[Dict[str, Any]]) -> SourceAction:
    entries = list(rows)
    first = entries[0] if entries else {}
    source_name = _clean(first.get("source_name"))
    category = _clean(first.get("category"))
    url = _clean(first.get("url"))
    failure_types = [ _clean(row.get("failure_type")) for row in entries ]
    statuses = [ _clean(row.get("status")) for row in entries ]
    markers = [ _clean(row.get("investigation_marker")) for row in entries ]
    http_statuses = [_to_int(row.get("http_status_code") or row.get("http_status"), 0) for row in entries]
    rfqs_found = max((_to_int(row.get("rfqs_found"), 0) for row in entries), default=0)
    qualified_rfqs = max((_to_int(row.get("qualified_rfqs"), 0) for row in entries), default=0)
    submission_candidates = max((_to_int(row.get("submission_candidates"), 0) for row in entries), default=0)
    reachable = any(_bool(row.get("reachable"), False) for row in entries)
    marker = next((value for value in markers if value), "")
    status = next((value for value in statuses if value), "unknown")
    failure_type = next((value for value in failure_types if value), "unknown_error")
    http_status_code = next((code for code in http_statuses if code > 0), None)

    if rfqs_found > 0 or qualified_rfqs > 0 or submission_candidates > 0:
        return SourceAction(
            source_name=source_name,
            category=category,
            url=url,
            action="promote",
            reason="Produced RFQs, qualified RFQs, or submission candidates.",
            failure_type=failure_type,
            status=status,
            reachable=reachable,
            rfqs_found=rfqs_found,
            qualified_rfqs=qualified_rfqs,
            submission_candidates=submission_candidates,
            http_status_code=http_status_code,
            investigation_marker=marker,
        )

    if marker == "dns_runtime_suspected":
        return SourceAction(
            source_name=source_name,
            category=category,
            url=url,
            action="investigate_runtime_dns",
            reason="Python DNS/runtime mismatch suspected; test in a clean runtime before quarantining.",
            failure_type=failure_type,
            status=status,
            reachable=reachable,
            rfqs_found=rfqs_found,
            qualified_rfqs=qualified_rfqs,
            submission_candidates=submission_candidates,
            http_status_code=http_status_code,
            investigation_marker=marker,
        )

    if failure_type == "no_candidates" or (reachable and rfqs_found == 0):
        return SourceAction(
            source_name=source_name,
            category=category,
            url=url,
            action="retry",
            reason="Reachable but no RFQs found; keep enabled and lower priority.",
            failure_type=failure_type,
            status=status,
            reachable=reachable,
            rfqs_found=rfqs_found,
            qualified_rfqs=qualified_rfqs,
            submission_candidates=submission_candidates,
            http_status_code=http_status_code,
            investigation_marker=marker,
        )

    if failure_type == "http_error":
        return SourceAction(
            source_name=source_name,
            category=category,
            url=url,
            action="investigate_http",
            reason="Likely bad endpoint, blocked path, SSL issue, redirect issue, login requirement, or blocked HEAD/GET behavior.",
            failure_type=failure_type,
            status=status,
            reachable=reachable,
            rfqs_found=rfqs_found,
            qualified_rfqs=qualified_rfqs,
            submission_candidates=submission_candidates,
            http_status_code=http_status_code,
            investigation_marker=marker,
        )

    if failure_type == "timeout":
        return SourceAction(
            source_name=source_name,
            category=category,
            url=url,
            action="investigate_timeout",
            reason="Retry with a longer timeout and lower concurrency.",
            failure_type=failure_type,
            status=status,
            reachable=reachable,
            rfqs_found=rfqs_found,
            qualified_rfqs=qualified_rfqs,
            submission_candidates=submission_candidates,
            http_status_code=http_status_code,
            investigation_marker=marker,
        )

    if failure_type in {"dns_failed", "unknown_error"} and marker != "dns_runtime_suspected":
        return SourceAction(
            source_name=source_name,
            category=category,
            url=url,
            action="quarantine_candidate",
            reason="Candidate only. Repeated dns_failed or unknown_error requires repeat clean-run validation before quarantine.",
            failure_type=failure_type,
            status=status,
            reachable=reachable,
            rfqs_found=rfqs_found,
            qualified_rfqs=qualified_rfqs,
            submission_candidates=submission_candidates,
            http_status_code=http_status_code,
            investigation_marker=marker,
        )

    return SourceAction(
        source_name=source_name,
        category=category,
        url=url,
        action="unknown_review",
        reason="Does not match a specific action rule.",
        failure_type=failure_type,
        status=status,
        reachable=reachable,
        rfqs_found=rfqs_found,
        qualified_rfqs=qualified_rfqs,
        submission_candidates=submission_candidates,
        http_status_code=http_status_code,
        investigation_marker=marker,
    )


def build_action_plan(input_path: Path = DEFAULT_INPUT_PATH) -> Dict[str, Any]:
    rows = _load_attempt_results(input_path)
    aggregated = _aggregate_source_rows(rows)
    classified = [classify_source(row["entries"]) for row in aggregated]

    by_action: Dict[str, List[SourceAction]] = defaultdict(list)
    for entry in classified:
        by_action[entry.action].append(entry)

    for entries in by_action.values():
        entries.sort(
            key=lambda row: (
                -row.rfqs_found,
                -row.qualified_rfqs,
                -row.submission_candidates,
                row.source_name.lower(),
            )
        )

    counts = Counter(entry.action for entry in classified)
    payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "input_path": str(input_path),
        "total_sources": len(classified),
        "counts": dict(counts),
        "sources": [entry.as_dict() for entry in classified],
    }
    return {
        "payload": payload,
        "by_action": by_action,
        "counts": counts,
    }


def _markdown_report(plan: Dict[str, Any]) -> str:
    counts: Counter = plan["counts"]
    by_action: Dict[str, List[SourceAction]] = plan["by_action"]
    lines = [
        "# Sprint 7 Source Action Plan",
        "",
        "No source was disabled by this classifier.",
        "",
        "## Action Counts",
        "",
        "| Action | Count |",
        "| --- | ---: |",
    ]
    for action in ["promote", "retry", "investigate_http", "investigate_timeout", "investigate_runtime_dns", "quarantine_candidate", "unknown_review"]:
        lines.append(f"| {action} | {counts.get(action, 0)} |")

    for action in ["promote", "retry", "investigate_http", "investigate_timeout", "investigate_runtime_dns", "quarantine_candidate", "unknown_review"]:
        lines.extend(["", f"## {action}", ""])
        rows = by_action.get(action, [])[:20]
        if not rows:
            lines.append("_No sources._")
            continue
        lines.append("| Source | Category | URL | RFQs | Qualified | Submission Candidates | Failure Type | HTTP | Marker |")
        lines.append("| --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- |")
        for row in rows:
            lines.append(
                f"| {row.source_name} | {row.category} | {row.url} | {row.rfqs_found} | {row.qualified_rfqs} | {row.submission_candidates} | {row.failure_type} | {row.http_status_code or ''} | {row.investigation_marker or ''} |"
            )
    return "\n".join(lines) + "\n"


def write_action_plan(
    *,
    input_path: Path = DEFAULT_INPUT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    plan = build_action_plan(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "source_action_plan.json"
    md_path = output_dir / "source_action_plan.md"
    json_path.write_text(json.dumps(plan["payload"], indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_markdown_report(plan), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "payload": plan["payload"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify Sprint 7 harvest-effectiveness sources")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT_PATH), help="Input source attempt results JSON")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Output directory for action plan artifacts")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    write_action_plan(input_path=Path(args.input), output_dir=Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
