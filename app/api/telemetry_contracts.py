from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List

from app.dashboard.dashboard_service import get_dashboard_summary
from app.dashboard.workflow_queue_service import (
    get_pending_approval_queue,
    get_proof_capture_queue,
    get_refused_queue,
    get_review_ready_queue,
)
from app.harvest.source_health import get_source_health
from app.harvest.source_registry import load_source_registry
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.reporting_service import build_operational_report
from app.monitoring.workflow_monitor import get_workflow_summary


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_province_distribution(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        normalized.append(
            {
                "code": _safe_str(row.get("code"), f"P{index:02d}"),
                "province": _safe_str(row.get("province"), "Unknown"),
                "rfqs": _safe_int(row.get("rfqs")),
                "eligible": _safe_int(row.get("eligible")),
                "value": _safe_float(row.get("value")),
                "avg_margin": _safe_float(row.get("avg_margin") or row.get("avgMargin")),
            }
        )
    return normalized


def _normalize_opportunity_breakdown(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "name": _safe_str(row.get("name"), "Unknown"),
                "value": _safe_int(row.get("value")),
            }
        )
    return normalized


def _normalize_top_high_profit_rfq(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _safe_str(row.get("title"), "Unknown RFQ"),
        "province": _safe_str(row.get("province"), "Unknown"),
        "value": _safe_str(row.get("value"), "R0"),
        "profit": _safe_str(row.get("profit"), "R0"),
    }


def _records_from_tender_analytics(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = summary.get("tender_success_analytics", {}).get("records", [])
    return [record for record in records if isinstance(record, dict)]


def _extract_record_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def build_dashboard_telemetry_response(limit: int = 100) -> Dict[str, Any]:
    try:
        summary = get_dashboard_summary(limit=limit)
        workflow_summary = _safe_dict(summary.get("workflow_summary"))
        quality_summary = _safe_dict(summary.get("quality_summary"))
        tender_analytics = _safe_dict(summary.get("tender_success_analytics"))
        qualification_result = _safe_dict(summary.get("qualification_result"))
        qualification_summary = _safe_dict(summary.get("qualification_summary"))
        pilot_metrics = _safe_dict(summary.get("pilot_metrics"))
        metrics = _safe_dict(summary.get("pilot_metrics"))
        records = _records_from_tender_analytics(summary)
        if not records:
            records = [_extract_record_payload(item) for item in _safe_list(tender_analytics.get("records"))]

        estimated_value = _safe_float(
            qualification_result.get("viability", {}).get("estimated_contract_value")
            or qualification_result.get("viability", {}).get("estimated_profit")
            or tender_analytics.get("tender_outcome_summary", {}).get("quotes_generated")
        )
        total_harvested = max(
            _safe_int(workflow_summary.get("total_workflows")),
            _safe_int(tender_analytics.get("tender_outcome_summary", {}).get("processed")),
            _safe_int(metrics.get("rfqs_processed")),
        )
        eligible_rfqs = max(
            _safe_int(tender_analytics.get("tender_outcome_summary", {}).get("eligible")),
            _safe_int(qualification_summary.get("recommendation_counts", {}).get("GO"))
            + _safe_int(qualification_summary.get("recommendation_counts", {}).get("MANUAL_REVIEW")),
        )
        average_margin = _safe_float(
            (qualification_result.get("viability", {}) or {}).get("gross_margin_ratio", 0.0) * 100.0
        )
        avg_profit = _safe_float(qualification_result.get("viability", {}).get("estimated_profit"))
        high_profit_rfqs = _safe_int(
            tender_analytics.get("tender_outcome_summary", {}).get("quotes_generated")
            or pilot_metrics.get("quote_generation_successes")
        )
        eligible_rate = round((eligible_rfqs / total_harvested) * 100.0, 2) if total_harvested else 0.0

        province_counter: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"rfqs": 0, "eligible": 0, "value": 0.0, "avg_margin_samples": []})
        opportunity_counter: Counter[str] = Counter()
        high_profit_rows: List[Dict[str, Any]] = []
        recent_alerts = []
        recent_alerts.extend(_safe_list(summary.get("pilot_warnings")))
        recent_alerts.extend(_safe_list(summary.get("operational_warnings")))
        recent_alerts.extend(_safe_list(quality_summary.get("quote_pack", {}).get("warnings")))
        recent_alerts = list(dict.fromkeys(_safe_str(item) for item in recent_alerts if _safe_str(item)))

        for record in records:
            payload = _extract_record_payload(record)
            province = _safe_str(payload.get("province") or record.get("province"), "Unknown")
            category = _safe_str(payload.get("category") or record.get("category"), "unknown")
            province_data = province_counter[province]
            province_data["rfqs"] += 1
            province_data["eligible"] += 1 if payload else 0
            province_data["value"] += _safe_float(payload.get("estimated_value") or payload.get("contract_value") or payload.get("value"))
            if payload.get("gross_margin_ratio") not in (None, ""):
                province_data["avg_margin_samples"].append(_safe_float(payload.get("gross_margin_ratio")) * 100.0)
            if category:
                opportunity_counter[category] += 1
            estimated_profit = _safe_float(payload.get("estimated_profit") or payload.get("profit_amount") or payload.get("profit"))
            if estimated_profit >= 30000:
                high_profit_rows.append(
                    {
                        "title": _safe_str(payload.get("title") or record.get("title"), "High profit RFQ"),
                        "province": province,
                        "value": _safe_str(payload.get("estimated_value") or payload.get("contract_value") or payload.get("value"), "R0"),
                        "profit": _safe_str(estimated_profit, "R0"),
                    }
                )

        province_distribution = []
        for province, data in province_counter.items():
            avg_margin_samples = data.pop("avg_margin_samples", [])
            province_distribution.append(
                {
                    "code": province[:2].upper() if province != "Unknown" else "UN",
                    "province": province,
                    "rfqs": int(data["rfqs"]),
                    "eligible": int(data["eligible"]),
                    "value": round(float(data["value"]), 2),
                    "avg_margin": round(mean(avg_margin_samples), 2) if avg_margin_samples else 0.0,
                }
            )

        opportunity_breakdown = [
            {"name": name, "value": value}
            for name, value in opportunity_counter.most_common()
        ]

        top_high_profit_rfqs = high_profit_rows[:5]
        if not top_high_profit_rfqs:
            top_high_profit_rfqs = [
                _normalize_top_high_profit_rfq(item)
                for item in _safe_list(quality_summary.get("supplier_pricing", {}).get("comparison_rows", []))[:5]
                if isinstance(item, dict)
            ]

        return {
            "status": "ok",
            "generated_at": _now_iso(),
            "data_source": "runtime",
            "total_harvested_rfqs": total_harvested,
            "eligible_rfqs": eligible_rfqs,
            "total_estimated_value": round(estimated_value, 2),
            "high_profit_rfqs": high_profit_rfqs,
            "avg_estimated_profit": round(avg_profit, 2),
            "avg_margin": round(average_margin, 2),
            "eligible_rate": eligible_rate,
            "province_distribution": province_distribution,
            "opportunity_breakdown": opportunity_breakdown,
            "top_high_profit_rfqs": top_high_profit_rfqs,
            "recent_alerts": recent_alerts[:10],
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "runtime_fallback",
            "total_harvested_rfqs": 0,
            "eligible_rfqs": 0,
            "total_estimated_value": 0.0,
            "high_profit_rfqs": 0,
            "avg_estimated_profit": 0.0,
            "avg_margin": 0.0,
            "eligible_rate": 0.0,
            "province_distribution": [],
            "opportunity_breakdown": [],
            "top_high_profit_rfqs": [],
            "recent_alerts": [],
        }


def build_source_health_telemetry_response(limit: int = 100) -> Dict[str, Any]:
    try:
        registry = load_source_registry()
        sources = list(registry.list_sources())[: max(1, int(limit or 100))]
        latest_failures = []
        total_response_times = []
        parser_failure_rates = []
        healthy = degraded = failing = disabled = 0
        for source in sources:
            health = get_source_health(source.id)
            status = _safe_str(health.status, "healthy")
            if status == "healthy":
                healthy += 1
            elif status == "degraded":
                degraded += 1
            elif status == "failing":
                failing += 1
            elif status == "disabled":
                disabled += 1
            total_response_times.append(_safe_float(health.average_response_time) * 1000.0)
            parser_failure_rates.append(_safe_float(health.parser_failure_rate))
            if health.last_failure:
                latest_failures.append(
                    {
                        "source_id": source.id,
                        "name": source.name,
                        "status": status,
                        "failure_count": _safe_int(health.failure_count),
                        "consecutive_failures": _safe_int(health.consecutive_failures),
                        "parser_failure_rate": _safe_float(health.parser_failure_rate),
                    }
                )
        total_sources = len(sources)
        active_sources = sum(1 for source in sources if source.is_active)
        average_response_time_ms = round(mean(total_response_times), 2) if total_response_times else 0.0
        average_parser_failure_rate = round(mean(parser_failure_rates), 4) if parser_failure_rates else 0.0
        return {
            "status": "ok",
            "generated_at": _now_iso(),
            "data_source": "runtime",
            "total_sources": total_sources,
            "active_sources": active_sources,
            "healthy_sources": healthy,
            "degraded_sources": degraded,
            "failing_sources": failing,
            "disabled_sources": disabled,
            "parser_failure_rate": average_parser_failure_rate,
            "average_response_time_ms": average_response_time_ms,
            "recent_source_failures": latest_failures[:10],
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "runtime_fallback",
            "total_sources": 0,
            "active_sources": 0,
            "healthy_sources": 0,
            "degraded_sources": 0,
            "failing_sources": 0,
            "disabled_sources": 0,
            "parser_failure_rate": 0.0,
            "average_response_time_ms": 0.0,
            "recent_source_failures": [],
        }


def _age_minutes(record: Dict[str, Any]) -> int:
    timestamp = _safe_str(record.get("updated_at") or record.get("created_at"))
    if not timestamp:
        return 0
    try:
        value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except Exception:
        return 0
    return max(0, int((datetime.now(timezone.utc) - value).total_seconds() / 60))


def build_review_queue_telemetry_response(limit: int = 100) -> Dict[str, Any]:
    try:
        pending_approval = get_pending_approval_queue(limit=limit)
        review_ready = get_review_ready_queue(limit=limit)
        proof_capture = get_proof_capture_queue(limit=limit)
        refused = get_refused_queue(limit=limit)
        workflow_summary = get_workflow_summary(limit=limit)
        queue_rows = pending_approval + review_ready + proof_capture
        operator_capacity = 1000
        operator_capacity_used = len(queue_rows)
        operator_capacity_remaining = max(0, operator_capacity - operator_capacity_used)
        queue_lag_minutes = max([_age_minutes(row) for row in queue_rows], default=0)
        overdue_reviews = sum(1 for row in queue_rows if _age_minutes(row) >= 24 * 60)
        approved_today = _safe_int(workflow_summary.get("approvals_pending")) + _safe_int(workflow_summary.get("review_ready_pending"))
        return {
            "status": "ok",
            "generated_at": _now_iso(),
            "data_source": "runtime",
            "pending_reviews": len(review_ready) + len(pending_approval),
            "approved_today": approved_today,
            "manual_review_required": len(review_ready) + len(pending_approval),
            "blocked_reviews": len(refused),
            "overdue_reviews": overdue_reviews,
            "operator_capacity": operator_capacity,
            "operator_capacity_used": operator_capacity_used,
            "operator_capacity_remaining": operator_capacity_remaining,
            "queue_lag_minutes": queue_lag_minutes,
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "runtime_fallback",
            "pending_reviews": 0,
            "approved_today": 0,
            "manual_review_required": 0,
            "blocked_reviews": 0,
            "overdue_reviews": 0,
            "operator_capacity": 1000,
            "operator_capacity_used": 0,
            "operator_capacity_remaining": 1000,
            "queue_lag_minutes": 0,
        }


def build_qualification_telemetry_response(limit: int = 100) -> Dict[str, Any]:
    try:
        summary = get_dashboard_summary(limit=limit)
        qualification_summary = _safe_dict(summary.get("qualification_summary"))
        qualification_result = _safe_dict(summary.get("qualification_result"))
        recommendation_counts = _safe_dict(qualification_summary.get("recommendation_counts"))
        manual_review_triggers = qualification_result.get("manual_review_triggers", [])
        disqualification_triggers = qualification_result.get("disqualification_triggers", [])
        risk_breakdown = _safe_dict(qualification_result.get("risk_breakdown"))
        low_confidence_count = 1 if qualification_result.get("readiness_state") in {"HIGH_RISK", "MISSING_DOCS", "MANUAL_ONLY"} else 0
        avg_risk_score = _safe_float(risk_breakdown.get("overall_risk") or risk_breakdown.get("overall_risk_score"))
        return {
            "status": "ok",
            "generated_at": _now_iso(),
            "data_source": "runtime",
            "go_count": _safe_int(recommendation_counts.get("GO")),
            "manual_review_count": _safe_int(recommendation_counts.get("MANUAL_REVIEW")),
            "reject_count": _safe_int(recommendation_counts.get("REJECT")),
            "low_confidence_count": low_confidence_count,
            "top_rejection_reasons": list(dict.fromkeys(_safe_list(qualification_result.get("blockers")) or _safe_list(disqualification_triggers)))[:10],
            "top_manual_review_triggers": list(dict.fromkeys(_safe_list(manual_review_triggers)))[:10],
            "avg_qualification_score": _safe_float(qualification_result.get("automation_suitability_score")),
            "avg_risk_score": avg_risk_score,
            "manualGovernanceOnly": True,
            "reviewReadyRequired": True,
            "proofCaptureRequired": True,
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "runtime_fallback",
            "go_count": 0,
            "manual_review_count": 0,
            "reject_count": 0,
            "low_confidence_count": 0,
            "top_rejection_reasons": [],
            "top_manual_review_triggers": [],
            "avg_qualification_score": 0.0,
            "avg_risk_score": 0.0,
            "manualGovernanceOnly": True,
            "reviewReadyRequired": True,
            "proofCaptureRequired": True,
        }


def build_operational_health_telemetry_response(limit: int = 100) -> Dict[str, Any]:
    try:
        dashboard_summary = get_dashboard_summary(limit=limit)
        operational_report = build_operational_report(limit=limit)
        metrics = _safe_dict(get_metrics_snapshot().get("metrics"))
        source_health = build_source_health_telemetry_response(limit=limit)
        review_queue = build_review_queue_telemetry_response(limit=limit)
        qualification = build_qualification_telemetry_response(limit=limit)
        source_failures = _safe_int(source_health.get("failing_sources")) + _safe_int(source_health.get("degraded_sources"))
        parser_failures = _safe_int(
            sum(
                1
                for item in source_health.get("recent_source_failures", [])
                if _safe_float(item.get("parserFailureRate") or item.get("parser_failure_rate")) > 0.1
            )
        )
        queue_lag = _safe_int(review_queue.get("queue_lag_minutes"))
        operator_capacity = _safe_int(review_queue.get("operator_capacity"), 1000)
        rfq_aging = max(0, _safe_int(dashboard_summary.get("workflow_summary", {}).get("total_workflows")) - _safe_int(dashboard_summary.get("workflow_summary", {}).get("approvals_pending")))
        stale_evidence = _safe_int(len(_safe_list(dashboard_summary.get("pilot_warnings"))) + len(_safe_list(dashboard_summary.get("operational_warnings"))))
        workflow_failures = _safe_int(metrics.get("workflow_failures"))
        persistence_failures = _safe_int(metrics.get("persistence_failures"))
        audit_failures = _safe_int(metrics.get("audit_failures"))
        status = "healthy"
        if source_failures or parser_failures or queue_lag or workflow_failures or persistence_failures or audit_failures:
            status = "degraded"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "data_source": "runtime",
            "source_failures": source_failures,
            "parser_failures": parser_failures,
            "queue_lag": queue_lag,
            "operator_capacity": operator_capacity,
            "rfq_aging": rfq_aging,
            "stale_evidence": stale_evidence,
            "workflow_failures": workflow_failures,
            "persistence_failures": persistence_failures,
            "audit_failures": audit_failures,
            "governance_compliance_score": _safe_float(operational_report.get("governance_compliance_score") or dashboard_summary.get("governance_compliance_score")),
            "manual_governance_integrity_score": _safe_float(operational_report.get("manual_governance_integrity_score") or dashboard_summary.get("manual_governance_integrity_score")),
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "runtime_fallback",
            "source_failures": 0,
            "parser_failures": 0,
            "queue_lag": 0,
            "operator_capacity": 1000,
            "rfq_aging": 0,
            "stale_evidence": 0,
            "workflow_failures": 0,
            "persistence_failures": 0,
            "audit_failures": 0,
            "governance_compliance_score": 0.0,
            "manual_governance_integrity_score": 0.0,
        }
