from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.operations.runtime_alerts import get_runtime_alerts
from app.productivity.review_efficiency_analytics import build_review_efficiency_analytics
from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary
from app.productivity.operator_workload_balancer import build_operator_workload_summary
from app.productivity.operator_focus_sessions import build_focus_session_summary

from ._shared import now_iso, safe_float, safe_int, safe_str


def build_operator_ux_feedback_report(limit: int = 200) -> Dict[str, Any]:
    alerts = get_runtime_alerts(limit=limit)
    queue = build_review_queue_optimization_summary(limit=limit)
    workload = build_operator_workload_summary(limit=limit)
    efficiency = build_review_efficiency_analytics(limit=limit)
    focus = build_focus_session_summary(limit=limit)

    pain_points: List[str] = []
    if safe_int(alerts.get("total", 0)) > 3:
        pain_points.append("Telemetry alert volume is high.")
    if safe_float(queue.get("summary", {}).get("average_queue_age_minutes", 0.0)) > 30:
        pain_points.append("Queue age is contributing to review friction.")
    if safe_int(efficiency.get("escalation_frequency", 0)) > 5:
        pain_points.append("Escalation frequency is adding operator friction.")
    if safe_int(workload.get("summary", {}).get("average_utilization", 0.0)) > 80:
        pain_points.append("Operator workload remains elevated.")
    stale_rfqs = len(queue.get("stale_rfqs", []))
    if stale_rfqs:
        pain_points.append("Stale RFQs are making the queue harder to clear.")
    if safe_int(focus.get("summary", {}).get("totalInterruptions", 0)) > 0:
        pain_points.append("Focus sessions are being interrupted.")

    trend_counts = Counter(
        [
            "alerts" if safe_int(alerts.get("total", 0)) else "quiet",
            "queue_age" if safe_float(queue.get("summary", {}).get("average_queue_age_minutes", 0.0)) > 30 else "queue_ok",
            "fatigue" if safe_float(workload.get("average_utilization", 0.0)) > 80 else "workload_ok",
            "interruptions" if safe_int(focus.get("summary", {}).get("totalInterruptions", 0)) else "focus_ok",
        ]
    )
    feedback_items = [
        {
            "topic": "queue friction",
            "severity": "warning" if stale_rfqs else "info",
            "message": "Queue optimization and evidence handling remain the primary friction points.",
        },
        {
            "topic": "telemetry noise",
            "severity": "warning" if safe_int(alerts.get("total", 0)) > 3 else "info",
            "message": "Alert volume should be kept readable for supervisors.",
        },
        {
            "topic": "focus interruptions",
            "severity": "info",
            "message": "Focus sessions are monitored for interruption bursts only.",
        },
    ]
    status = "healthy" if not pain_points else "degraded"
    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime",
        "pain_points": pain_points,
        "trend_summary": dict(trend_counts),
        "feedback_items": feedback_items,
        "operational_signals": {
            "alerts": alerts,
            "queue": queue,
            "workload": workload,
            "efficiency": efficiency,
            "focus": focus,
        },
    }

