from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.analytics.tender_success_analytics import build_tender_success_analytics
from app.dashboard.dashboard_service import get_dashboard_summary
from app.harvest.source_health import get_source_health
from app.harvest.source_registry import load_source_registry
from app.monitoring.health_service import get_system_health
from app.monitoring.reporting_service import build_operational_report
from app.monitoring.workflow_monitor import get_workflow_summary
from app.orchestration.job_history import get_job_history
from app.persistence.repositories import WorkflowRepository, get_persistence_health
from app.pricing_evidence import build_pricing_traceability, build_supplier_quote_evidence, validate_pricing_evidence
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.qualification.qualification_engine import build_qualification_summary, qualify_rfq


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


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


def _workflow_repo() -> WorkflowRepository:
    return WorkflowRepository()


def _workflow_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = record.get("details") or record.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def _latest_workflow_records(limit: int = 100) -> List[Dict[str, Any]]:
    records = _workflow_repo().fetch_recent(limit=limit)
    latest: Dict[str, Dict[str, Any]] = {}
    for record in reversed(records):
        tender_id = _safe_str(record.get("tender_id"))
        if tender_id and tender_id not in latest:
            latest[tender_id] = record
    return list(latest.values())


def _default_rows() -> List[Dict[str, Any]]:
    try:
        dashboard = get_dashboard_summary(limit=50)
        qualification = _safe_dict(dashboard.get("qualification_result"))
        workflow_summary = _safe_dict(dashboard.get("workflow_summary"))
    except Exception:
        qualification = {}
        workflow_summary = {}
    return [
        {
            "tender_id": _safe_str(qualification.get("tender_id"), "RFQ-001"),
            "title": "RFQ Detail Unavailable",
            "buyer": "Unknown",
            "province": "Unknown",
            "qualification_state": qualification.get("recommendation", "MANUAL_REVIEW"),
            "estimated_profit": _safe_float(qualification.get("viability", {}).get("estimated_profit")),
            "estimated_margin": round(_safe_float(qualification.get("viability", {}).get("gross_margin_ratio")) * 100.0, 2),
            "risk_level": qualification.get("risk_level", "medium"),
            "workflow_stage": _safe_str(workflow_summary.get("latest_stage"), "unknown"),
            "review_status": "manual_review_required",
            "pricing_confidence": _safe_float(qualification.get("pricing_confidence", {}).get("overall_pricing_confidence")),
            "source_tier": "Tier 4",
            "submission_method": _safe_str(qualification.get("submission_method", {}).get("method"), "unknown"),
            "data_source": "fallback",
            "last_updated": _now_iso(),
        }
    ]


def get_operator_workflow_rows(limit: int = 100) -> Dict[str, Any]:
    try:
        records = _latest_workflow_records(limit=limit)
        rows: List[Dict[str, Any]] = []
        for record in records:
            payload = _workflow_payload(record)
            qualification = qualify_rfq(payload) if payload else {}
            pricing_evidence = build_supplier_quote_evidence(payload.get("pricing_evidence") or payload.get("supplier_quote") or {}) if payload else {}
            pricing_traceability = build_pricing_traceability(payload.get("pricing_evidence") or payload.get("supplier_quote") or {}, evidence_report=pricing_evidence) if payload else {}
            title = _safe_str(payload.get("title") or payload.get("description") or record.get("tender_id"), "Unknown RFQ")
            buyer = _safe_str(payload.get("buyer_name") or payload.get("buyer"), "Unknown")
            province = _safe_str(payload.get("province"), "Unknown")
            workflow_stage = _safe_str(record.get("stage"), "unknown")
            source_tier = _safe_str(payload.get("source_tier"), "Tier 4")
            if source_tier.lower().startswith("tier"):
                source_tier = source_tier.title()
            else:
                source_tier = f"Tier {source_tier}"
            rows.append(
                {
                    "tender_id": _safe_str(record.get("tender_id")),
                    "title": title,
                    "buyer": buyer,
                    "province": province,
                    "qualification_state": qualification.get("recommendation", "MANUAL_REVIEW"),
                    "estimated_profit": _safe_float(qualification.get("viability", {}).get("estimated_profit") or payload.get("estimated_profit")),
                    "estimated_margin": round(_safe_float(qualification.get("viability", {}).get("gross_margin_ratio") or payload.get("gross_margin_ratio")) * 100.0, 2),
                    "risk_level": qualification.get("risk_level", "medium"),
                    "workflow_stage": workflow_stage,
                    "review_status": "review_ready" if workflow_stage in {"approved", "review_ready"} else "manual_review_required" if workflow_stage in {"approval_required", "extracted", "evaluated", "priced"} else "unknown",
                    "pricing_confidence": _safe_float(qualification.get("pricing_confidence", {}).get("overall_pricing_confidence") or pricing_evidence.get("evidence_completeness_score")),
                    "source_tier": source_tier,
                    "submission_method": _safe_str(qualification.get("submission_method", {}).get("method") or payload.get("submission_method"), "unknown"),
                    "data_source": "runtime",
                    "last_updated": _safe_str(record.get("updated_at") or record.get("created_at")),
                    "qualification": qualification,
                    "pricing_evidence": pricing_evidence,
                    "pricing_traceability": pricing_traceability,
                }
            )
        if not rows:
            rows = _default_rows()
        summary = {
            "total": len(rows),
            "go": sum(1 for row in rows if row.get("qualification_state") == "GO"),
            "manual_review": sum(1 for row in rows if row.get("qualification_state") == "MANUAL_REVIEW"),
            "reject": sum(1 for row in rows if row.get("qualification_state") == "REJECT"),
            "data_source": "runtime" if records else "fallback",
        }
        return {"status": "ok", "generated_at": _now_iso(), "data_source": summary["data_source"], "summary": summary, "rows": rows[: max(1, int(limit or 100))]}
    except Exception:
        return {"status": "degraded", "generated_at": _now_iso(), "data_source": "fallback", "summary": {"total": 0, "go": 0, "manual_review": 0, "reject": 0, "data_source": "fallback"}, "rows": _default_rows()}


def get_operator_workflow_detail(tender_id: str) -> Dict[str, Any]:
    try:
        workflow = _workflow_repo().fetch_latest_state(tender_id)
        history = _workflow_repo().fetch_history(tender_id, limit=100)
        payload = _workflow_payload(workflow)
        qualification = qualify_rfq(payload) if payload else {}
        pricing_evidence_payload = payload.get("pricing_evidence") or payload.get("supplier_quote") or {}
        pricing_evidence = build_supplier_quote_evidence(pricing_evidence_payload) if pricing_evidence_payload else {}
        pricing_validation = validate_pricing_evidence(pricing_evidence_payload) if pricing_evidence_payload else {}
        pricing_traceability = build_pricing_traceability(pricing_evidence_payload, evidence_report=pricing_evidence, validation_report=pricing_validation) if pricing_evidence_payload else {}
        source_id = _safe_str(payload.get("source_id") or payload.get("source_url"))
        source_health = get_source_health(source_id).to_jsonable_dict() if source_id else {}
        return {
            "status": "ok",
            "generated_at": _now_iso(),
            "data_source": "runtime" if workflow else "fallback",
            "tender_id": tender_id,
            "summary": {
                "title": _safe_str(payload.get("title") or workflow.get("details", {}).get("title") or tender_id, "Unknown RFQ"),
                "buyer": _safe_str(payload.get("buyer_name") or workflow.get("details", {}).get("buyer_name"), "Unknown"),
                "province": _safe_str(payload.get("province") or workflow.get("details", {}).get("province"), "Unknown"),
                "workflow_stage": _safe_str(workflow.get("stage"), "unknown"),
                "review_status": "review_ready" if qualification.get("readiness_state") == "READY" else "manual_review_required",
            },
            "qualification_summary": qualification,
            "risk_summary": qualification.get("risk_breakdown", {}),
            "pricing_evidence": pricing_evidence,
            "pricing_validation": pricing_validation,
            "pricing_traceability": pricing_traceability,
            "governance_summary": {
                "manual_approval_status": qualification.get("recommendation") != "REJECT",
                "review_ready_status": qualification.get("readiness_state") == "READY",
                "proof_capture_status": qualification.get("submission_readiness", {}).get("readiness_state") in {"READY", "HIGH_RISK"},
                "supervised_live_governance": True,
                "manual_submission_confirmed": False,
                "governance_compliance_score": _safe_float(build_pilot_readiness_report().get("governance_compliance_score", 0.0)),
            },
            "workflow_history": history,
            "operational_warnings": qualification.get("warnings", []),
            "recommendation_reasons": qualification.get("recommendation_reasons", []),
            "manual_review_triggers": qualification.get("manual_review_triggers", []),
            "disqualification_triggers": qualification.get("disqualification_triggers", []),
            "source_health": source_health,
            "data_source_label": "runtime" if workflow else "fallback",
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "fallback",
            "tender_id": tender_id,
            "summary": {
                "title": "Unknown RFQ",
                "buyer": "Unknown",
                "province": "Unknown",
                "workflow_stage": "unknown",
                "review_status": "manual_review_required",
            },
            "qualification_summary": {},
            "risk_summary": {},
            "pricing_evidence": {},
            "pricing_validation": {},
            "pricing_traceability": {},
            "governance_summary": {
                "manual_approval_status": False,
                "review_ready_status": False,
                "proof_capture_status": False,
                "supervised_live_governance": True,
                "manual_submission_confirmed": False,
                "governance_compliance_score": 0.0,
            },
            "workflow_history": [],
            "operational_warnings": [],
            "recommendation_reasons": [],
            "manual_review_triggers": [],
            "disqualification_triggers": [],
            "source_health": {},
            "data_source_label": "fallback",
        }


def get_qualification_insights(limit: int = 100) -> Dict[str, Any]:
    workflow_rows = get_operator_workflow_rows(limit=limit).get("rows", [])
    qualification_results = [row.get("qualification", {}) for row in workflow_rows if isinstance(row, dict)]
    summary = build_qualification_summary(qualification_results)
    data_source = "runtime" if any(_safe_str(row.get("data_source")) == "runtime" for row in workflow_rows) else "fallback"
    province_heat: Dict[str, Dict[str, int]] = defaultdict(lambda: {"GO": 0, "MANUAL_REVIEW": 0, "REJECT": 0})
    low_confidence_rows = []
    for row in workflow_rows:
        province = _safe_str(row.get("province"), "Unknown")
        recommendation = _safe_str(row.get("qualification_state"), "MANUAL_REVIEW")
        province_heat[province][recommendation] = province_heat[province].get(recommendation, 0) + 1
        if recommendation != "GO" or _safe_float(row.get("pricing_confidence")) < 55.0:
            low_confidence_rows.append(row)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": data_source,
        "summary": summary,
        "province_heat": province_heat,
        "low_confidence_rfqs": low_confidence_rows[:20],
        "risk_distribution": Counter(row.get("risk_level", "medium") for row in workflow_rows),
        "qualification_score_average": summary.get("average_automation_suitability_score", 0.0),
        "risk_score_average": summary.get("risk_breakdown", {}).get("overall_risk", 0.0) if isinstance(summary.get("risk_breakdown"), dict) else 0.0,
        "top_rejection_reasons": summary.get("blockers", []),
        "top_manual_review_triggers": list(summary.get("manual_review_trigger_counts", {}).keys())[:20],
        "go_count": summary.get("recommendation_counts", {}).get("GO", 0),
        "manual_review_count": summary.get("recommendation_counts", {}).get("MANUAL_REVIEW", 0),
        "reject_count": summary.get("recommendation_counts", {}).get("REJECT", 0),
    }


def get_pricing_evidence_overview(limit: int = 100) -> Dict[str, Any]:
    workflow_rows = get_operator_workflow_rows(limit=limit).get("rows", [])
    data_source = "runtime" if any(_safe_str(row.get("data_source")) == "runtime" for row in workflow_rows) else "fallback"
    evidence_rows = []
    anomalies = Counter()
    stale_count = 0
    vat_mismatch_count = 0
    subtotal_mismatch_count = 0
    delivery_inconsistency_count = 0
    for row in workflow_rows:
        pricing_evidence = _safe_dict(row.get("pricing_evidence"))
        pricing_traceability = _safe_dict(row.get("pricing_traceability"))
        pricing_validation = _safe_dict((row.get("qualification") or {}).get("pricing_validation"))
        evidence_rows.append(
            {
                "tender_id": row.get("tender_id"),
                "title": row.get("title"),
                "supplier_evidence_score": pricing_evidence.get("evidence_completeness_score", 0.0),
                "pricing_defensibility_score": pricing_evidence.get("pricing_defensibility_score", 0.0),
                "pricing_confidence": _safe_float(row.get("pricing_confidence")),
                "quote_age_days": pricing_traceability.get("quote_age_days", 0),
                "risk_level": pricing_traceability.get("risk_level", "medium"),
                "operator_override_notes": pricing_traceability.get("operator_override_notes", ""),
                "traceability_chain": pricing_traceability.get("traceability_chain", []),
            }
        )
        stale_count += 1 if pricing_traceability.get("risk_level") == "HIGH_RISK" else 0
        vat_mismatch_count += len(_safe_list(pricing_validation.get("validation_errors")))
        subtotal_mismatch_count += sum(1 for warning in _safe_list(pricing_validation.get("validation_warnings")) if "subtotal" in str(warning).lower())
        delivery_inconsistency_count += sum(1 for warning in _safe_list(pricing_validation.get("validation_warnings")) if "delivery" in str(warning).lower())
        for warning in _safe_list(pricing_validation.get("validation_warnings")):
            anomalies[str(warning)] += 1
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": data_source,
        "summary": {
            "supplier_quote_completeness_average": round(sum(row["supplier_evidence_score"] for row in evidence_rows) / max(len(evidence_rows), 1), 2),
            "pricing_defensibility_average": round(sum(row["pricing_defensibility_score"] for row in evidence_rows) / max(len(evidence_rows), 1), 2),
            "pricing_confidence_average": round(sum(row["pricing_confidence"] for row in evidence_rows) / max(len(evidence_rows), 1), 2),
            "stale_quote_count": stale_count,
            "vat_mismatch_count": vat_mismatch_count,
            "subtotal_mismatch_count": subtotal_mismatch_count,
            "delivery_inconsistency_count": delivery_inconsistency_count,
        },
        "pricing_evidence_rows": evidence_rows[:50],
        "pricing_anomalies": [{"name": name, "count": count} for name, count in anomalies.most_common(20)],
    }


def get_source_health_details(limit: int = 100) -> Dict[str, Any]:
    try:
        registry = load_source_registry()
        sources = registry.list_sources()[: max(1, int(limit or 100))]
        rows: List[Dict[str, Any]] = []
        tier_breakdown = Counter()
        for source in sources:
            health = get_source_health(source.id)
            rows.append(
                {
                    "source_id": source.id,
                    "name": source.name,
                    "source_tier": str(getattr(source, "source_tier", "tier_4")),
                    "parser_type": source.parser_type,
                    "status": health.status,
                    "last_success": _safe_str(health.last_success),
                    "last_failure": _safe_str(health.last_failure),
                    "failure_count": health.failure_count,
                    "average_response_time_ms": round(_safe_float(health.average_response_time) * 1000.0, 2),
                    "parser_failure_rate": _safe_float(health.parser_failure_rate),
                    "health_state": "healthy" if health.status == "healthy" else "degraded" if health.status == "degraded" else "failing" if health.status == "failing" else "disabled",
                }
            )
            tier_breakdown[str(getattr(source, "source_tier", "tier_4"))] += 1
        return {
            "status": "ok",
            "generated_at": _now_iso(),
            "data_source": "persistence" if rows else "fallback",
            "rows": rows,
            "tier_breakdown": dict(tier_breakdown),
            "summary": {
                "total_sources": len(rows),
                "healthy_sources": sum(1 for row in rows if row["status"] == "healthy"),
                "degraded_sources": sum(1 for row in rows if row["status"] == "degraded"),
                "failing_sources": sum(1 for row in rows if row["status"] == "failing"),
                "disabled_sources": sum(1 for row in rows if row["status"] == "disabled"),
            },
        }
    except Exception:
        return {
            "status": "degraded",
            "generated_at": _now_iso(),
            "data_source": "fallback",
            "rows": [],
            "tier_breakdown": {},
            "summary": {
                "total_sources": 0,
                "healthy_sources": 0,
                "degraded_sources": 0,
                "failing_sources": 0,
                "disabled_sources": 0,
            },
        }
