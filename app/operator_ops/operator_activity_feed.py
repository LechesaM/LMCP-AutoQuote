from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.operator_ops.operator_action_models import OperatorTimelineEvent


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timeline_path() -> Path:
    return get_runtime_paths().manual_production_file("operator_timeline.jsonl")


def _append(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _timeline_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def append_timeline_event(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = OperatorTimelineEvent.validate_payload(event).to_jsonable_dict()
    payload.setdefault("created_at", _now_iso())
    return _append(payload)


def get_operator_timeline(limit: int = 100) -> Dict[str, Any]:
    path = _timeline_path()
    if not path.exists():
        return {"status": "ok", "generated_at": _now_iso(), "data_source": "fallback", "events": [], "total": 0}
    events: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                events.append(payload)
    except Exception:
        return {"status": "degraded", "generated_at": _now_iso(), "data_source": "fallback", "events": [], "total": 0}
    items = list(reversed(events[-max(1, int(limit or 100)):]))
    return {"status": "ok", "generated_at": _now_iso(), "data_source": "runtime" if items else "fallback", "events": items, "total": len(events)}
