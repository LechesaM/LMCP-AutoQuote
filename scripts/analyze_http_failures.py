from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime_paths import get_runtime_paths


DEFAULT_INPUT_PATH = get_runtime_paths().runtime_root / "harvest_effectiveness" / "source_action_plan.json"
DEFAULT_OUTPUT_DIR = get_runtime_paths().runtime_root / "harvest_effectiveness"
HTTP_BUCKETS = [
    "HTTP 301",
    "HTTP 302",
    "HTTP 401",
    "HTTP 403",
    "HTTP 404",
    "HTTP 405",
    "HTTP 500",
    "SSL Error",
    "Redirect Loop",
    "Unknown HTTP",
]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_action_plan(path: Path = DEFAULT_INPUT_PATH) -> Dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "generated_at": _now_iso(), "total_sources": 0, "counts": {}, "sources": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"status": "invalid", "generated_at": _now_iso(), "total_sources": 0, "counts": {}, "sources": []}
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []
    sources = [row for row in sources if isinstance(row, dict)]
    payload["sources"] = sources
    return payload


def _curl_head_probe(url: str, timeout: int) -> Dict[str, Any]:
    if not _clean(url):
        return {"status": "unknown", "http_status_code": None, "error_message": "missing_url", "raw_output": ""}
    command = " ".join(
        [
            "curl",
            "-sS",
            "-I",
            "-L",
            "--max-time",
            str(max(1, int(timeout))),
            shlex.quote(url),
        ]
    )
    completed = subprocess.run(["/bin/zsh", "-lc", command], capture_output=True, text=True, check=False)
    combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    http_status_code = None
    for line in combined.splitlines():
        text = line.strip()
        if text.upper().startswith("HTTP/"):
            parts = text.split()
            for part in parts[1:]:
                if part.isdigit():
                    http_status_code = int(part)
                    break
            if http_status_code is not None:
                break
    return {
        "returncode": completed.returncode,
        "http_status_code": http_status_code,
        "error_message": combined.strip()[:400],
        "raw_output": combined.strip(),
    }


def _classify_http_bucket(http_status_code: Optional[int], error_message: str) -> str:
    message = _clean(error_message).lower()
    if any(term in message for term in ("ssl", "certificate", "tls", "handshake")):
        return "SSL Error"
    if any(term in message for term in ("too many redirects", "maximum (number of) redirects", "redirect loop", "redirect")) and (http_status_code is None or http_status_code in {301, 302, 303, 307, 308}):
        return "Redirect Loop"
    if http_status_code == 301:
        return "HTTP 301"
    if http_status_code == 302:
        return "HTTP 302"
    if http_status_code == 401:
        return "HTTP 401"
    if http_status_code == 403:
        return "HTTP 403"
    if http_status_code == 404:
        return "HTTP 404"
    if http_status_code == 405:
        return "HTTP 405"
    if http_status_code == 500:
        return "HTTP 500"
    return "Unknown HTTP"


@dataclass(frozen=True)
class HTTPFailureRow:
    source_name: str
    category: str
    url: str
    bucket: str
    http_status_code: Optional[int]
    error_message: str
    action: str
    investigation_marker: str
    reachable: bool
    rfqs_found: int
    qualified_rfqs: int
    submission_candidates: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "category": self.category,
            "url": self.url,
            "bucket": self.bucket,
            "http_status_code": self.http_status_code,
            "error_message": self.error_message,
            "action": self.action,
            "investigation_marker": self.investigation_marker,
            "reachable": self.reachable,
            "rfqs_found": self.rfqs_found,
            "qualified_rfqs": self.qualified_rfqs,
            "submission_candidates": self.submission_candidates,
        }


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


def analyze_http_failures(
    *,
    input_path: Path = DEFAULT_INPUT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    timeout: int = 20,
    probe_fn: Callable[[str, int], Dict[str, Any]] = _curl_head_probe,
) -> Dict[str, Any]:
    action_plan = _load_action_plan(input_path)
    sources = [row for row in action_plan.get("sources", []) if _clean(row.get("action")) == "investigate_http"]

    rows: List[HTTPFailureRow] = []
    for source in sources:
        url = _clean(source.get("url"))
        probe = probe_fn(url, timeout)
        http_status_code = probe.get("http_status_code")
        if http_status_code is not None:
            try:
                http_status_code = int(http_status_code)
            except Exception:
                http_status_code = None
        bucket = _classify_http_bucket(http_status_code, _clean(probe.get("error_message")))
        rows.append(
            HTTPFailureRow(
                source_name=_clean(source.get("source_name")),
                category=_clean(source.get("category")),
                url=url,
                bucket=bucket,
                http_status_code=http_status_code,
                error_message=_clean(probe.get("error_message")),
                action=_clean(source.get("action")),
                investigation_marker=_clean(source.get("investigation_marker")),
                reachable=_bool(probe.get("reachable"), False),
                rfqs_found=_to_int(source.get("rfqs_found"), 0),
                qualified_rfqs=_to_int(source.get("qualified_rfqs"), 0),
                submission_candidates=_to_int(source.get("submission_candidates"), 0),
            )
        )

    counts = Counter(row.bucket for row in rows)
    by_bucket: Dict[str, List[HTTPFailureRow]] = defaultdict(list)
    for row in rows:
        by_bucket[row.bucket].append(row)
    for bucket_rows in by_bucket.values():
        bucket_rows.sort(key=lambda row: (row.source_name.lower(), row.url))

    payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "input_path": str(input_path),
        "total_investigate_http_sources": len(rows),
        "counts": {bucket: counts.get(bucket, 0) for bucket in HTTP_BUCKETS},
        "sources": [row.as_dict() for row in rows],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "http_failure_summary.json"
    md_path = output_dir / "http_failure_summary.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_markdown(payload, by_bucket), encoding="utf-8")

    docs_path = get_runtime_paths().project_root / "docs" / "operations_validation_pack" / "sprint_7_http_failure_analysis.md"
    docs_path.write_text(
        "\n".join(
            [
                "# Sprint 7 HTTP Failure Analysis",
                "",
                "This analysis classifies the `investigate_http` sources from the Sprint 7 action plan.",
                "",
                f"- Input: `{input_path}`",
                f"- Generated at: `{payload['generated_at']}`",
                f"- Output JSON: `{json_path}`",
                f"- Output Markdown: `{md_path}`",
                "",
                "No source was disabled by this analysis.",
                "",
                "## Current Counts",
                "",
                "| Bucket | Count |",
                "| --- | ---: |",
            ]
            + [f"| {bucket} | {payload['counts'].get(bucket, 0)} |" for bucket in HTTP_BUCKETS]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "payload": payload,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "docs_path": str(docs_path),
    }


def _build_markdown(payload: Dict[str, Any], by_bucket: Dict[str, List[HTTPFailureRow]]) -> str:
    lines = [
        "# Sprint 7 HTTP Failure Summary",
        "",
        "No source was disabled by this analysis.",
        "",
        "## Counts",
        "",
        "| Bucket | Count |",
        "| --- | ---: |",
    ]
    for bucket in HTTP_BUCKETS:
        lines.append(f"| {bucket} | {payload['counts'].get(bucket, 0)} |")

    for bucket in HTTP_BUCKETS:
        lines.extend(["", f"## {bucket}", ""])
        rows = by_bucket.get(bucket, [])[:20]
        if not rows:
            lines.append("_No sources._")
            continue
        lines.append("| Source | Category | URL | HTTP | Reachable | RFQs | Qualified | Submission Candidates |")
        lines.append("| --- | --- | --- | ---: | --- | ---: | ---: | ---: |")
        for row in rows:
            lines.append(
                f"| {row.source_name} | {row.category} | {row.url} | {row.http_status_code or ''} | {str(row.reachable).lower()} | {row.rfqs_found} | {row.qualified_rfqs} | {row.submission_candidates} |"
            )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Sprint 7 HTTP failures")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT_PATH), help="Source action plan JSON")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Output directory for summaries")
    parser.add_argument("--timeout", type=int, default=20, help="Per-source curl timeout in seconds")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    analyze_http_failures(input_path=Path(args.input), output_dir=Path(args.output_dir), timeout=max(1, int(args.timeout or 20)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
