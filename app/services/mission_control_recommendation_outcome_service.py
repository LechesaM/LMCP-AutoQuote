from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths


_LOCK = Lock()
ALLOWED_OUTCOMES = {"created", "submitted", "won", "lost", "no_action"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text or default
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_date(value: Any) -> datetime.date | None:
    text = _safe_str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _history_root() -> Path:
    explicit = _safe_str(os.getenv("LMCP_MISSION_CONTROL_TRACKING_DIR") or os.getenv("LMCP_MISSION_CONTROL_OUTCOME_DIR"))
    if explicit:
        return Path(explicit).expanduser().resolve()
    return get_runtime_paths().runtime_root / "mission_control"


def _outcome_log_path() -> Path:
    explicit = _safe_str(os.getenv("LMCP_MISSION_CONTROL_OUTCOME_LOG_PATH"))
    if explicit:
        return Path(explicit).expanduser().resolve()
    return _history_root() / "recommendation_outcomes.jsonl"


def _normalise_outcome(value: Any) -> str:
    text = _safe_str(value, "no_action").lower()
    return text if text in ALLOWED_OUTCOMES else "no_action"


def _dedupe_key(record: Dict[str, Any]) -> str:
    recommendation_id = _safe_str(record.get("recommendationId") or record.get("recommendation_id") or record.get("id"))
    outcome = _safe_str(record.get("outcome") or "no_action").lower()
    recorded_at = _safe_str(record.get("recordedAt") or record.get("recorded_at") or _now_iso())
    date_key = _safe_date(recorded_at)
    return "|".join([recommendation_id, outcome, date_key.isoformat() if date_key else recorded_at[:10]])


def _read_outcomes() -> List[Dict[str, Any]]:
    path = _outcome_log_path()
    if not path.exists():
        return []
    outcomes: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                outcomes.append(payload)
    except Exception:
        return []
    return outcomes


def _write_outcome(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _outcome_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def build_default_mission_control_recommendation_outcome_summary(status: str = "insufficient_history") -> Dict[str, Any]:
    return {
        "status": status,
        "generatedAt": _now_iso(),
        "days": 30,
        "totals": {
            "outcomes": 0,
            "created": 0,
            "submitted": 0,
            "won": 0,
            "lost": 0,
            "no_action": 0,
        },
        "byOutcome": {"created": 0, "submitted": 0, "won": 0, "lost": 0, "no_action": 0},
        "byRecommendationType": {},
        "recentOutcomes": [],
        "outcomeLogPath": str(_outcome_log_path()),
    }


def record_mission_control_recommendation_outcome(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _safe_dict(payload)
    outcome = _normalise_outcome(data.get("outcome"))
    recorded_at = _safe_str(data.get("recordedAt") or data.get("recorded_at") or _now_iso())
    recommendation_id = _safe_str(data.get("recommendationId") or data.get("recommendation_id") or data.get("id") or _dedupe_key(data))
    record = {
        "id": _safe_str(data.get("id") or f"mc-rec-outcome-{len(_read_outcomes()) + 1}"),
        "recommendationId": recommendation_id,
        "recommendationType": _safe_str(data.get("recommendationType") or data.get("recommendation_type") or "unknown").lower(),
        "outcome": outcome,
        "daysToOutcome": int(_safe_float(data.get("daysToOutcome") or data.get("days_to_outcome") or 0)),
        "estimatedProfit": _safe_float(data.get("estimatedProfit") or data.get("estimated_profit") or 0),
        "actualProfit": data.get("actualProfit") if data.get("actualProfit") is not None else data.get("actual_profit"),
        "recordedAt": recorded_at,
    }

    existing = _read_outcomes()
    key = _dedupe_key(record)
    if any(_dedupe_key(item) == key for item in existing):
        return record
    return _write_outcome(record)


def build_mission_control_recommendation_outcome_summary(days: int = 30) -> Dict[str, Any]:
    try:
        window_days = max(1, min(int(days or 30), 365))
    except Exception:
        window_days = 30

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=window_days - 1)
    outcomes = [item for item in _read_outcomes() if _safe_date(item.get("recordedAt") or item.get("recorded_at")) is not None]
    outcomes = [item for item in outcomes if _safe_date(item.get("recordedAt") or item.get("recorded_at")) >= cutoff]
    outcomes.sort(key=lambda item: _safe_str(item.get("recordedAt") or item.get("recorded_at")), reverse=True)

    if not outcomes:
        return build_default_mission_control_recommendation_outcome_summary()

    by_outcome = Counter(_normalise_outcome(item.get("outcome")) for item in outcomes)
    by_recommendation_type: Dict[str, Counter[str]] = defaultdict(Counter)
    for item in outcomes:
        recommendation_type = _safe_str(item.get("recommendationType") or item.get("recommendation_type") or "unknown").lower()
        outcome = _normalise_outcome(item.get("outcome"))
        by_recommendation_type[recommendation_type][outcome] += 1

    recommendation_type_metrics = {}
    for recommendation_type, counts in by_recommendation_type.items():
        generated = counts.get("created", 0) + counts.get("submitted", 0) + counts.get("won", 0) + counts.get("lost", 0) + counts.get("no_action", 0)
        submitted = counts.get("submitted", 0)
        won = counts.get("won", 0)
        lost = counts.get("lost", 0)
        no_action = counts.get("no_action", 0)
        recommendation_type_metrics[recommendation_type] = {
            "recommendationType": recommendation_type,
            "generated": generated,
            "created": counts.get("created", 0),
            "submitted": submitted,
            "won": won,
            "lost": lost,
            "no_action": no_action,
            "completionRate": round((won / generated) * 100.0, 2) if generated else 0.0,
            "actionRate": round(((submitted + won + lost) / generated) * 100.0, 2) if generated else 0.0,
        }

    recent_outcomes = outcomes[:20]
    return {
        "status": "configured",
        "generatedAt": _now_iso(),
        "days": window_days,
        "totals": {
            "outcomes": len(outcomes),
            "created": by_outcome.get("created", 0),
            "submitted": by_outcome.get("submitted", 0),
            "won": by_outcome.get("won", 0),
            "lost": by_outcome.get("lost", 0),
            "no_action": by_outcome.get("no_action", 0),
        },
        "byOutcome": {key: by_outcome.get(key, 0) for key in ("created", "submitted", "won", "lost", "no_action")},
        "byRecommendationType": recommendation_type_metrics,
        "recentOutcomes": recent_outcomes,
        "outcomeLogPath": str(_outcome_log_path()),
    }
