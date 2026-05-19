from __future__ import annotations

from typing import Any, Dict


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _band(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def assess_pricing_confidence(
    payload: Dict[str, Any],
    *,
    evidence_report: Dict[str, Any] | None = None,
    validation_report: Dict[str, Any] | None = None,
    quote_aging_report: Dict[str, Any] | None = None,
    supplier_match: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    data = dict(payload or {})
    evidence_report = evidence_report or {}
    validation_report = validation_report or {}
    quote_aging_report = quote_aging_report or {}
    supplier_match = supplier_match or {}

    evidence_score = _safe_float(evidence_report.get("evidence_completeness_score"), 0.0)
    defensibility_score = _safe_float(evidence_report.get("pricing_defensibility_score"), evidence_score)
    supplier_confidence_score = max(0.0, min(100.0, round((evidence_score * 0.6) + (defensibility_score * 0.4), 2)))

    pricing_confidence_score = 100.0
    if not evidence_report:
        pricing_confidence_score -= 35.0
    if str(evidence_report.get("quotation_source_type") or "").lower() in {"estimated/manual", "manual"}:
        pricing_confidence_score -= 20.0
    if not evidence_report.get("vat_clarity"):
        pricing_confidence_score -= 12.0
    if not evidence_report.get("delivery_assumptions"):
        pricing_confidence_score -= 10.0
    if validation_report.get("validation_errors"):
        pricing_confidence_score -= min(35.0, 10.0 + len(validation_report.get("validation_errors", [])) * 8.0)
    elif validation_report.get("validation_warnings"):
        pricing_confidence_score -= min(20.0, len(validation_report.get("validation_warnings", [])) * 4.0)
    if quote_aging_report.get("quote_expiry_risk") == "expired":
        pricing_confidence_score -= 25.0
    elif quote_aging_report.get("aging_severity") == "high":
        pricing_confidence_score -= 15.0
    elif quote_aging_report.get("stale_pricing_warnings"):
        pricing_confidence_score -= 8.0
    if supplier_match.get("logistics_complexity") == "high":
        pricing_confidence_score -= 10.0
    elif supplier_match.get("logistics_complexity") == "medium":
        pricing_confidence_score -= 4.0
    if supplier_match.get("delivery_feasibility") == "low":
        pricing_confidence_score -= 8.0
    if not data.get("delivery_assumptions") and not evidence_report.get("delivery_assumptions"):
        pricing_confidence_score -= 8.0
    if evidence_report.get("evidence_warnings"):
        pricing_confidence_score -= min(12.0, len(evidence_report.get("evidence_warnings", [])) * 2.0)

    logistics_confidence_score = 100.0
    logistics_confidence_score -= 20.0 if supplier_match.get("logistics_complexity") == "high" else 8.0 if supplier_match.get("logistics_complexity") == "medium" else 0.0
    logistics_confidence_score -= 10.0 if quote_aging_report.get("quote_expiry_risk") == "expired" else 4.0 if quote_aging_report.get("aging_severity") == "high" else 0.0
    logistics_confidence_score -= 8.0 if not evidence_report.get("delivery_assumptions") else 0.0
    logistics_confidence_score -= 6.0 if supplier_match.get("supplier_evidence_required") else 0.0

    delivery_confidence_score = 100.0
    delivery_confidence_score -= 18.0 if not evidence_report.get("delivery_assumptions") else 0.0
    delivery_confidence_score -= 12.0 if quote_aging_report.get("quote_expiry_risk") == "expired" else 6.0 if quote_aging_report.get("aging_severity") == "high" else 0.0
    delivery_confidence_score -= 8.0 if any("delivery inconsistency" in str(item).lower() for item in validation_report.get("validation_warnings", [])) else 0.0

    overall = round(
        max(
            0.0,
            min(
                100.0,
                (pricing_confidence_score * 0.4)
                + (supplier_confidence_score * 0.25)
                + (logistics_confidence_score * 0.2)
                + (delivery_confidence_score * 0.15),
            ),
        ),
        2,
    )
    return {
        "supplier_confidence_score": round(max(0.0, min(100.0, supplier_confidence_score)), 2),
        "pricing_confidence_score": round(max(0.0, min(100.0, pricing_confidence_score)), 2),
        "logistics_confidence_score": round(max(0.0, min(100.0, logistics_confidence_score)), 2),
        "delivery_confidence_score": round(max(0.0, min(100.0, delivery_confidence_score)), 2),
        "overall_pricing_confidence": overall,
        "confidence_band": _band(overall),
        "supplier_evidence_score": evidence_score,
        "pricing_defensibility_score": defensibility_score,
        "advisory_only": True,
    }


def build_pricing_confidence_summary(reports: Dict[str, Any] | None = None) -> Dict[str, Any]:
    report = reports or {}
    overall = _safe_float(report.get("overall_pricing_confidence"), 0.0)
    return {
        "overall_pricing_confidence": overall,
        "confidence_band": _band(overall),
        "supplier_confidence_score": _safe_float(report.get("supplier_confidence_score"), 0.0),
        "pricing_confidence_score": _safe_float(report.get("pricing_confidence_score"), 0.0),
        "logistics_confidence_score": _safe_float(report.get("logistics_confidence_score"), 0.0),
        "delivery_confidence_score": _safe_float(report.get("delivery_confidence_score"), 0.0),
        "advisory_only": True,
    }
