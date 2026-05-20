from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.operator_ops.operator_activity_feed import get_operator_timeline


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def build_focus_session_summary(limit: int = 200) -> Dict[str, Any]:
    events = get_operator_timeline(limit=limit).get("events", [])
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[str(event.get("operator_id") or "unassigned")].append(event)

    sessions: List[Dict[str, Any]] = []
    for operator_id, rows in grouped.items():
        timestamps = [_parse_iso(item.get("created_at") or item.get("updated_at")) for item in rows]
        timestamps = [value for value in timestamps if value]
        if not timestamps:
            continue
        timestamps.sort()
        interruptions = 0
        bursts = 0
        window_start = timestamps[0]
        last_seen = timestamps[0]
        for timestamp in timestamps[1:]:
            gap = (timestamp - last_seen).total_seconds() / 60.0
            if gap <= 15:
                bursts += 1
            else:
                interruptions += 1
                window_start = timestamp
            last_seen = timestamp
        sessions.append(
            {
                "operator_id": operator_id,
                "focused_minutes": round((timestamps[-1] - timestamps[0]).total_seconds() / 60.0, 2),
                "review_throughput": len(rows),
                "interruption_count": interruptions,
                "completion_bursts": bursts,
                "session_start": timestamps[0].isoformat(),
                "session_end": timestamps[-1].isoformat(),
            }
        )

    return {
        "status": "ok" if sessions else "fallback",
        "generated_at": _now_iso(),
        "data_source": "runtime" if sessions else "fallback",
        "sessions": sessions,
        "summary": {
            "sessionCount": len(sessions),
            "totalThroughput": sum(session["review_throughput"] for session in sessions),
            "totalInterruptions": sum(session["interruption_count"] for session in sessions),
            "totalBursts": sum(session["completion_bursts"] for session in sessions),
        },
        "advisory_only": True,
    }
