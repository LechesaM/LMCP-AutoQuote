from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths


SECRET_PATTERNS = (
    re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]+"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(text: str) -> str:
    value = str(text or "")
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _read_jsonl(path: Path, limit: int = 200) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                items.append(payload)
    except Exception:
        return []
    return items[-max(1, int(limit or 200)) :]


def build_log_aggregation_summary(limit: int = 200) -> Dict[str, Any]:
    paths = get_runtime_paths()
    sources = {
        "operations": _read_jsonl(paths.manual_production_file("operations_logs.jsonl"), limit=limit),
        "incidents": _read_jsonl(paths.manual_production_file("runtime_incidents.jsonl"), limit=limit),
        "metrics": _read_jsonl(paths.manual_production_file("runtime_metrics.jsonl"), limit=limit),
    }
    records: List[Dict[str, Any]] = []
    for source_name, source_records in sources.items():
        for record in source_records:
            entry = dict(record)
            entry["source"] = source_name
            records.append(entry)

    categories = Counter()
    severities = Counter()
    for record in records:
        categories[str(record.get("category") or record.get("incident_type") or record.get("type") or "runtime")] += 1
        severities[str(record.get("severity") or "info")] += 1

    redacted_samples = []
    for record in records[-5:]:
        redacted_samples.append(_redact(json.dumps(record, ensure_ascii=False, default=str)))

    return {
        "status": "ok" if records else "fallback",
        "generated_at": _now_iso(),
        "data_source": "runtime" if records else "fallback",
        "total_logs": len(records),
        "log_sources": {name: len(items) for name, items in sources.items()},
        "category_counts": dict(categories),
        "severity_distribution": dict(severities),
        "redacted_samples": redacted_samples,
    }
