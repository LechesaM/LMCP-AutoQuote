from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple

from app.analytics.tender_success_analytics import build_tender_success_analytics
from app.dashboard.dashboard_service import get_dashboard_summary
from app.harvest.operator_capacity import capacity_status
from app.harvest.source_health import get_source_health
from app.harvest.source_tiers import HarvestTier
from app.harvest.source_registry import load_source_registry
from app.monitoring.health_service import get_system_health
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.reporting_service import build_operational_report
from app.monitoring.workflow_monitor import get_workflow_summary
from app.orchestration.queue_monitor import get_queue_health, get_queue_summary
from app.dashboard.workflow_queue_service import (
    get_pending_approval_queue,
    get_proof_capture_queue,
    get_refused_queue,
    get_review_ready_queue,
)
from app.persistence.repositories import WorkflowRepository, get_persistence_health
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.qualification.qualification_engine import build_qualification_summary, qualify_rfq


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


def _data_source(*sources: str) -> str:
    normalized = {str(source).strip().lower() for source in sources if str(source).strip()}
    normalized.discard("ok")
    if not normalized:
        return "fallback"
    if normalized == {"runtime"}:
        return "runtime"
    if normalized == {"persistence"}:
        return "persistence"
    if normalized == {"fallback"}:
        return "fallback"
    return "mixed"


def _source_tier_text(value: Any) -> str:
    tier = HarvestTier.from_value(value)
    if tier == HarvestTier.TIER_1:
        return "Tier 1"
    if tier == HarvestTier.TIER_2:
        return "Tier 2"
    if tier == HarvestTier.TIER_3:
        return "Tier 3"
    return "Tier 4"


def _workflow_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = record.get("details") or record.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def _qualification_results(limit: int = 100) -> Tuple[List[Dict[str, Any]], str]:
    results: List[Dict[str, Any]] = []
    source_tags: List[str] = []
    records = build_tender_success_analytics(limit=limit).get("records", [])
    if records:
        source_tags.append("persistence")
    for record in records:
        if not isinstance(record, dict):
            continue
        payload = _safe_dict(record.get("payload")) or _safe_dict(record.get("details")) or record
        if not payload:
            continue
        result = qualify_rfq(payload)
        if result:
            results.append(result)
    if not results:
        summary = get_dashboard_summary(limit=limit)
        qualification_result = _safe_dict(summary.get("qualification_result"))
        if qualification_result:
            results.append(qualification_result)
            source_tags.append("runtime")
    if not source_tags:
        source_tags.append("fallback")
    return results, _data_source(*source_tags)


def get_live_dashboard_telemetry(limit: int = 100) -> Dict[str, Any]:
    try:
        dashboard_summary = get_dashboard_summary(limit=limit)
        workflow_summary = _safe_dict(dashboard_summary.get("workflow_summary"))
        pilot_readiness = _safe_dict(build_pilot_readiness_report(limit=limit))
        tender_analytics = _safe_dict(dashboard_summary.get("tender_success_analytics"))
        qualification_results, qualification_source = _qualification_results(limit=limit)
        qualification_summary = build_qualification_summary(qualification_results)
        quality_summary = _safe_dict(dashboard_summary.get("quality_summary"))
        records = _safe_list(tender_analytics.get("records"))
        source_registry = load_source_registry()
        source_count = len(source_registry.list_sources())

        if not records and qualification_results:
            records = [{"payload": result, "tender_id": result.get("tender_id", "")} for result in qualification_results]

        province_counter: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"rfqs": 0, "eligible": 0, "value": 0.0, "avg_margin_samples": []})
        opportunity_counter: Counter[str] = Counter()
        high_profit_rows: List[Dict[str, Any]] = []
        total_estimated_value = 0.0
        estimated_profits: List[float] = []
        margin_samples: List[float] = []
        for record in records:
            payload = _workflow_payload(record)
            result = qualify_rfq(payload) if payload else {}
            province = _safe_str(payload.get("province") or record.get("province") or result.get("classification", {}).get("province"), "Unknown")
            category = _safe_str(result.get("category") or payload.get("category_guess") or payload.get("category"), "unknown")
            estimated_value = _safe_float(
                result.get("viability", {}).get("estimated_contract_value")
                or payload.get("estimated_contract_value")
                or payload.get("estimated_value")
                or payload.get("contract_value")
            )
            estimated_profit = _safe_float(
                result.get("viability", {}).get("estimated_profit")
                or payload.get("estimated_profit")
                or payload.get("profit_amount")
                or payload.get("profit")
            )
            gross_margin_ratio = _safe_float(
                result.get("viability", {}).get("gross_margin_ratio")
                or payload.get("gross_margin_ratio")
                or payload.get("margin_ratio")
            )
            province_data = province_counter[province]
            province_data["rfqs"] += 1
            province_data["eligible"] += 1 if result.get("recommendation") != "REJECT" else 0
            province_data["value"] += estimated_value
            if gross_margin_ratio:
                province_data["avg_margin_samples"].append(gross_margin_ratio * 100.0)
                margin_samples.append(gross_margin_ratio * 100.0)
            if category:
                opportunity_counter[category] += 1
            if estimated_profit:
                estimated_profits.append(estimated_profit)
            total_estimated_value += estimated_value
            if estimated_profit >= 30000:
                high_profit_rows.append(
                    {
                        "title": _safe_str(payload.get("title") or record.get("title") or result.get("tender_id"), "High profit RFQ"),
                        "province": province,
                        "value": _safe_str(estimated_value, "R0"),
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

        if not province_distribution and source_count:
            province_distribution = [
                {
                    "code": "NA",
                    "province": "Unavailable",
                    "rfqs": source_count,
                    "eligible": 0,
                    "value": 0.0,
                    "avg_margin": 0.0,
                }
            ]

        opportunity_breakdown = [{"name": name, "value": value} for name, value in opportunity_counter.most_common()]
        if not opportunity_breakdown and source_count:
            opportunity_breakdown = [{"name": "sources", "value": source_count}]

        recommendation_counts = _safe_dict(qualification_summary.get("recommendation_counts"))
        eligible_rfqs = _safe_int(recommendation_counts.get("GO")) + _safe_int(recommendation_counts.get("MANUAL_REVIEW"))
        total_harvested = max(
            _safe_int(workflow_summary.get("total_workflows")),
            _safe_int(tender_analytics.get("tender_outcome_summary", {}).get("processed")),
            len(records),
            len(qualification_results),
        )
        avg_estimated_profit = round(mean(estimated_profits), 2) if estimated_profits else 0.0
        avg_margin = round(mean(margin_samples), 2) if margin_samples else _safe_float(
            qualification_results[0].get("viability", {}).get("gross_margin_ratio", 0.0) * 100.0 if qualification_results else 0.0
        )
        recent_alerts = []
        recent_alerts.extend(_safe_list(dashboard_summary.get("pilot_warnings")))
        recent_alerts.extend(_safe_list(dashboard_summary.get("operational_warnings")))
        recent_alerts.extend(_safe_list(pilot_readiness.get("warnings")))
        recent_alerts.extend(_safe_list(quality_summary.get("quote_pack", {}).get("warnings")))
        recent_alerts.extend(_safe_list(tender_analytics.get("blocker_frequency")))
        recent_alerts = list(dict.fromkeys(_safe_str(item.get("blocker") if isinstance(item, dict) else item) for item in recent_alerts if _safe_str(item.get("blocker") if isinstance(item, dict) else item)))

        source_tags = ["runtime", "persistence"] if records else ["runtime"]
        if qualification_source:
            source_tags.append(qualification_source)

        high_profit_rows = high_profit_rows[:5]
        if not high_profit_rows and qualification_results:
            for result in qualification_results[:5]:
                high_profit_rows.append(
                    {
                        "title": _safe_str(result.get("tender_id") or result.get("classification", {}).get("category"), "High profit RFQ"),
                        "province": _safe_str(result.get("submission_method", {}).get("target_address"), "Unknown"),
                        "value": _safe_str(result.get("viability", {}).get("estimated_contract_value"), "R0"),
                        "profit": _safe_str(result.get("viability", {}).get("estimated_profit"), "R0"),
                    }
                )

        return {
            "status": "ok" if total_harvested or source_count else "degraded",
            "generated_at": _now_iso(),
            "data_source": _data_source(*source_tags),
            "total_harvested_rfqs": total_harvested,
            "eligible_rfqs": eligible_rfqs,
            "total_estimated_value": round(total_estimated_value, 2),
            "high_profit_rfqs": len(high_profit_rows),
            "avg_estimated_profit": avg_estimated_profit,
            "avg_margin": avg_margin,
            "eligible_rate": round((eligible_rfqs / total_harvested) * 100.0, 2) if total_harvested else 0.0,
            "province_distribution": province_distribution,
            "opportunity_breakdown": opportunity_breakdown,
            "top_high_profit_rfqs": high_profit_rows,
            "recent_alerts": recent_alerts[:10],
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "fallback",
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


def get_live_source_health_telemetry(limit: int = 100) -> Dict[str, Any]:
    try:
        registry = load_source_registry()
        sources = list(registry.list_sources())[: max(1, int(limit or 100))]
        latest_failures = []
        total_response_times = []
        parser_failure_rates = []
        tier_breakdown: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "active": 0, "healthy": 0, "degraded": 0, "failing": 0, "disabled": 0})
        healthy = degraded = failing = disabled = 0
        for source in sources:
            health = get_source_health(source.id)
            status = _safe_str(health.status, "healthy")
            tier_name = _source_tier_text(getattr(source, "source_tier", "Tier 4"))
            tier_bucket = tier_breakdown[tier_name]
            tier_bucket["total"] += 1
            if source.is_active:
                tier_bucket["active"] += 1
            if status == "healthy":
                healthy += 1
                tier_bucket["healthy"] += 1
            elif status == "degraded":
                degraded += 1
                tier_bucket["degraded"] += 1
            elif status == "failing":
                failing += 1
                tier_bucket["failing"] += 1
            elif status == "disabled":
                disabled += 1
                tier_bucket["disabled"] += 1
            total_response_times.append(_safe_float(health.average_response_time) * 1000.0)
            parser_failure_rates.append(_safe_float(health.parser_failure_rate))
            if health.last_failure or status in {"degraded", "failing", "disabled"}:
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
            "status": "ok" if total_sources else "degraded",
            "generated_at": _now_iso(),
            "data_source": "persistence" if total_sources else "fallback",
            "total_sources": total_sources,
            "active_sources": active_sources,
            "healthy_sources": healthy,
            "degraded_sources": degraded,
            "failing_sources": failing,
            "disabled_sources": disabled,
            "parser_failure_rate": average_parser_failure_rate,
            "average_response_time_ms": average_response_time_ms,
            "recent_source_failures": latest_failures[:10],
            "tier_breakdown": dict(tier_breakdown),
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "fallback",
            "total_sources": 0,
            "active_sources": 0,
            "healthy_sources": 0,
            "degraded_sources": 0,
            "failing_sources": 0,
            "disabled_sources": 0,
            "parser_failure_rate": 0.0,
            "average_response_time_ms": 0.0,
            "recent_source_failures": [],
            "tier_breakdown": {},
        }


def get_live_review_queue_telemetry(limit: int = 100) -> Dict[str, Any]:
    try:
        pending_approval = get_pending_approval_queue(limit=limit)
        review_ready = get_review_ready_queue(limit=limit)
        proof_capture = get_proof_capture_queue(limit=limit)
        refused = get_refused_queue(limit=limit)
        queue_health = get_queue_health(limit=limit)
        queue_summary = get_queue_summary(limit=limit)
        queue_rows = pending_approval + review_ready + proof_capture
        capacity = capacity_status(already_promoted_count=len(queue_rows))
        queue_lag_minutes = max([_age_minutes(row) for row in queue_rows], default=0)
        overdue_reviews = sum(1 for row in queue_rows if _age_minutes(row) >= 24 * 60)
        approved_today = _safe_int(queue_summary.get("completed_jobs")) or len(review_ready)
        blocked_reviews = len(refused) + _safe_int(queue_summary.get("blocked_jobs"))
        source_data = "persistence" if queue_rows or queue_summary else "fallback"
        return {
            "status": "ok" if queue_rows else "degraded",
            "generated_at": _now_iso(),
            "data_source": source_data,
            "pending_reviews": len(pending_approval) + len(review_ready),
            "approved_today": approved_today,
            "manual_review_required": len(pending_approval) + len(review_ready),
            "blocked_reviews": blocked_reviews,
            "overdue_reviews": overdue_reviews,
            "operator_capacity": capacity.total_daily_review_capacity,
            "operator_capacity_used": len(queue_rows),
            "operator_capacity_remaining": capacity.remaining_capacity,
            "queue_lag_minutes": queue_lag_minutes,
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "fallback",
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


def get_live_qualification_telemetry(limit: int = 100) -> Dict[str, Any]:
    try:
        results, source_data = _qualification_results(limit=limit)
        summary = build_qualification_summary(results)
        if not results:
            summary = build_qualification_summary([])
        top_rejection_counter: Counter[str] = Counter()
        top_manual_review_counter: Counter[str] = Counter()
        risk_scores: List[float] = []
        for item in results:
            for blocker in item.get("blockers", []):
                top_rejection_counter[_safe_str(blocker)] += 1
            for trigger in item.get("manual_review_triggers", []):
                top_manual_review_counter[_safe_str(trigger)] += 1
            if item.get("risk_breakdown", {}).get("overall_risk") is not None:
                risk_scores.append(_safe_float(item.get("risk_breakdown", {}).get("overall_risk")))
            elif item.get("risk_level") == "high":
                risk_scores.append(90.0)
            elif item.get("risk_level") == "medium":
                risk_scores.append(55.0)
            else:
                risk_scores.append(20.0)
        low_confidence_count = sum(
            1
            for item in results
            if item.get("readiness_state") in {"HIGH_RISK", "MISSING_DOCS", "MANUAL_ONLY"}
            or item.get("manual_pricing_review_required")
            or item.get("stale_quote_warning")
        )
        return {
            "status": "ok" if results else "degraded",
            "generated_at": _now_iso(),
            "data_source": source_data,
            "go_count": _safe_int(summary.get("recommendation_counts", {}).get("GO")),
            "manual_review_count": _safe_int(summary.get("recommendation_counts", {}).get("MANUAL_REVIEW")),
            "reject_count": _safe_int(summary.get("recommendation_counts", {}).get("REJECT")),
            "low_confidence_count": low_confidence_count,
            "top_rejection_reasons": [item for item, _count in top_rejection_counter.most_common(10)] or _safe_list(summary.get("blockers"))[:10],
            "top_manual_review_triggers": [item for item, _count in top_manual_review_counter.most_common(10)] or list(_safe_dict(summary.get("manual_review_trigger_counts")).keys())[:10],
            "avg_qualification_score": _safe_float(summary.get("average_automation_suitability_score")),
            "avg_risk_score": round(mean(risk_scores), 2) if risk_scores else 0.0,
            "manualGovernanceOnly": True,
            "reviewReadyRequired": True,
            "proofCaptureRequired": True,
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "fallback",
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


def get_live_operational_health_telemetry(limit: int = 100) -> Dict[str, Any]:
    try:
        dashboard_summary = get_dashboard_summary(limit=limit)
        operational_report = build_operational_report(limit=limit)
        system_health = _safe_dict(get_system_health())
        metrics = _safe_dict(get_metrics_snapshot().get("metrics"))
        source_health = get_live_source_health_telemetry(limit=limit)
        review_queue = get_live_review_queue_telemetry(limit=limit)
        qualification = get_live_qualification_telemetry(limit=limit)
        persistence = get_persistence_health()
        workflow_summary = _safe_dict(get_workflow_summary(limit=limit))
        queue_health = _safe_dict(get_queue_health(limit=limit))
        queue_summary = _safe_dict(get_queue_summary(limit=limit))
        source_failures = _safe_int(source_health.get("failing_sources")) + _safe_int(source_health.get("degraded_sources"))
        parser_failures = _safe_int(
            sum(1 for item in source_health.get("recent_source_failures", []) if _safe_float(item.get("parser_failure_rate")) > 0.1)
        )
        queue_lag = _safe_int(review_queue.get("queue_lag_minutes") or queue_health.get("stalled", {}).get("count", 0))
        operator_capacity = _safe_int(review_queue.get("operator_capacity"), 1000)
        rfq_aging = max(
            0,
            _safe_int(workflow_summary.get("total_workflows"))
            - _safe_int(workflow_summary.get("approvals_pending"))
            - _safe_int(queue_summary.get("queued_jobs")),
        )
        stale_evidence = _safe_int(len(_safe_list(dashboard_summary.get("pilot_warnings"))) + len(_safe_list(dashboard_summary.get("operational_warnings"))))
        workflow_failures = _safe_int(metrics.get("workflow_failures"))
        persistence_failures = _safe_int(metrics.get("persistence_failures")) + _safe_int(persistence.get("write_failures")) + _safe_int(persistence.get("read_failures"))
        audit_failures = _safe_int(metrics.get("audit_failures")) + len(_safe_list(operational_report.get("runtime_diagnostics", {}).get("warnings")))
        status = "healthy"
        if workflow_failures or persistence_failures or audit_failures:
            status = "failing"
        elif source_failures or parser_failures or queue_lag or stale_evidence:
            status = "degraded"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "data_source": _data_source("runtime", "persistence"),
            "source_failures": source_failures,
            "parser_failures": parser_failures,
            "queue_lag": queue_lag,
            "operator_capacity": operator_capacity,
            "rfq_aging": rfq_aging,
            "stale_evidence": stale_evidence,
            "workflow_failures": workflow_failures,
            "persistence_failures": persistence_failures,
            "audit_failures": audit_failures,
            "governance_compliance_score": _safe_float(
                operational_report.get("governance_compliance_score") or dashboard_summary.get("governance_compliance_score")
            ),
            "manual_governance_integrity_score": _safe_float(
                operational_report.get("manual_governance_integrity_score") or dashboard_summary.get("manual_governance_integrity_score")
            ),
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "fallback",
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
