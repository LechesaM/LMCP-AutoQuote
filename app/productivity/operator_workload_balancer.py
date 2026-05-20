from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Tuple

from app.operator_ops.operator_assignment_service import get_operator_assignments
from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot
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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _operator_label(record: Dict[str, Any]) -> str:
    return str(record.get("operator_id") or record.get("operatorId") or "unassigned")


def _assignment_status(record: Dict[str, Any]) -> str:
    return str(record.get("status") or "assigned").lower()


def _assumed_specialization(record: Dict[str, Any]) -> str:
    details = record.get("details") if isinstance(record.get("details"), dict) else {}
    return str(details.get("specialization") or details.get("category") or details.get("source") or "general")


def build_operator_workload_summary(limit: int = 200) -> Dict[str, Any]:
    assignments = get_operator_assignments(limit=max(1, int(limit or 200))).get("assignments", [])
    capacity = get_operator_capacity_snapshot()
    timeline = get_operator_timeline(limit=max(1, int(limit or 200))).get("events", [])
    now = datetime.now(timezone.utc)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in assignments:
        grouped[_operator_label(record)].append(record)

    timeline_counts = Counter(str(item.get("operator_id") or item.get("operatorId") or "unassigned") for item in timeline)
    operator_rows: List[Dict[str, Any]] = []
    overload_warnings: List[str] = []
    underutilization_warnings: List[str] = []

    for operator_id, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        overdue = 0
        priorities = []
        specializations = Counter()
        due_ages: List[float] = []
        for row in rows:
            priorities.append(_safe_int(row.get("priority"), 0))
            specializations[_assumed_specialization(row)] += 1
            due_at = _parse_iso(row.get("due_at") or row.get("dueAt"))
            if due_at:
                due_ages.append(max(0.0, (now - due_at).total_seconds() / 3600.0))
                if due_at < now and _assignment_status(row) not in {"completed", "reviewed", "archived"}:
                    overdue += 1
        assigned = len(rows)
        utilization = round((assigned / max(1, _safe_int(capacity.get("per_operator_daily_capacity", 100)))) * 100.0, 2)
        workload_score = round((assigned * 10.0) + (overdue * 25.0) + (mean(priorities) if priorities else 0.0), 2)
        specialization = specializations.most_common(1)[0][0] if specializations else "general"
        if assigned > _safe_int(capacity.get("per_operator_daily_capacity", 100)):
            overload_warnings.append(f"{operator_id} is over daily capacity")
        if assigned and assigned < 3:
            underutilization_warnings.append(f"{operator_id} is lightly loaded")
        operator_rows.append(
            {
                "operator_id": operator_id,
                "assigned": assigned,
                "overdue": overdue,
                "utilization": utilization,
                "timeline_events": timeline_counts.get(operator_id, 0),
                "specialization": specialization,
                "workload_score": workload_score,
                "average_due_age_hours": round(mean(due_ages), 2) if due_ages else 0.0,
                "priority_average": round(mean(priorities), 2) if priorities else 0.0,
            }
        )

    if not operator_rows:
        operator_rows = [
            {
                "operator_id": f"operator-{index + 1}",
                "assigned": 0,
                "overdue": 0,
                "utilization": 0.0,
                "timeline_events": 0,
                "specialization": "general",
                "workload_score": 0.0,
                "average_due_age_hours": 0.0,
                "priority_average": 0.0,
            }
            for index in range(_safe_int(capacity.get("team_size", 10), 10))
        ]

    return {
        "status": "ok" if not overload_warnings else "degraded",
        "generated_at": _now_iso(),
        "data_source": "runtime" if assignments else "fallback",
        "team_size": _safe_int(capacity.get("team_size", 10), 10),
        "total_daily_capacity": _safe_int(capacity.get("total_daily_capacity", 1000), 1000),
        "assigned_today": _safe_int(capacity.get("assigned_today", len(assignments))),
        "remaining_capacity": _safe_int(capacity.get("remaining_capacity", 1000)),
        "overload_warnings": overload_warnings,
        "underutilization_warnings": underutilization_warnings,
        "operators": operator_rows,
        "average_utilization": round(mean([row["utilization"] for row in operator_rows]) if operator_rows else 0.0, 2),
        "average_workload_score": round(mean([row["workload_score"] for row in operator_rows]) if operator_rows else 0.0, 2),
    }


def recommend_workload_rebalance(limit: int = 200) -> Dict[str, Any]:
    summary = build_operator_workload_summary(limit=limit)
    operators = list(summary.get("operators", []))
    operators.sort(key=lambda row: (-float(row.get("workload_score", 0.0)), str(row.get("operator_id") or "")))
    return {
        "status": summary.get("status", "ok"),
        "generated_at": summary.get("generated_at", _now_iso()),
        "data_source": summary.get("data_source", "fallback"),
        "recommendations": [
            {
                "operator_id": row.get("operator_id"),
                "recommendation": "rebalance" if float(row.get("utilization", 0.0)) > 100.0 else "monitor",
                "reason": "high overload" if float(row.get("utilization", 0.0)) > 100.0 else "within capacity",
                "workload_score": row.get("workload_score", 0.0),
            }
            for row in operators[:10]
        ],
        "warnings": summary.get("overload_warnings", []) + summary.get("underutilization_warnings", []),
    }
