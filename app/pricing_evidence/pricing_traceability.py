from __future__ import annotations

from typing import Any, Dict, List


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _first_line(payload: Dict[str, Any]) -> Dict[str, Any]:
    items = payload.get("lines") or payload.get("line_items") or []
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def build_pricing_traceability(
    payload: Dict[str, Any],
    *,
    evidence_report: Dict[str, Any] | None = None,
    validation_report: Dict[str, Any] | None = None,
    quote_aging_report: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    data = dict(payload or {})
    evidence_report = evidence_report or {}
    validation_report = validation_report or {}
    quote_aging_report = quote_aging_report or {}
    line = _first_line(data)
    final_quoted_amount = (
        data.get("final_quoted_amount")
        or data.get("grand_total")
        or data.get("total")
        or validation_report.get("provided_total")
        or validation_report.get("computed_total")
        or 0.0
    )
    traceability_chain: List[Dict[str, Any]] = [
        {
            "step": "rfq_item",
            "source": _safe_str(line.get("description") or data.get("item") or data.get("title"), "unknown"),
            "evidence_reference": _safe_str(data.get("tender_id") or data.get("quote_reference"), "unknown"),
            "detail": "line item linked to pricing evidence",
            "append_only": True,
        },
        {
            "step": "supplier_source",
            "source": _safe_str(evidence_report.get("quotation_source_type") or data.get("quotation_source_type"), "unknown"),
            "evidence_reference": _safe_str(evidence_report.get("quote_reference") or data.get("quote_reference"), "unknown"),
            "detail": _safe_str(evidence_report.get("supplier_name") or data.get("supplier_name"), "supplier not specified"),
            "append_only": True,
        },
        {
            "step": "supplier_evidence_reference",
            "source": _safe_str(evidence_report.get("supplier_contact") or data.get("supplier_contact"), "unknown"),
            "evidence_reference": _safe_str(evidence_report.get("quote_reference") or data.get("quote_reference"), "unknown"),
            "detail": f"evidence completeness {evidence_report.get('evidence_completeness_score', 0.0)}",
            "append_only": True,
        },
        {
            "step": "markup_source",
            "source": _safe_str(data.get("markup_source") or data.get("pricing_mode") or "manual"),
            "evidence_reference": _safe_str(data.get("markup_reference") or data.get("pricing_reference"), "not provided"),
            "detail": "markup remains operator-controlled",
            "append_only": True,
        },
        {
            "step": "delivery_cost_assumption",
            "source": "delivery assumptions",
            "evidence_reference": _safe_str(data.get("delivery_cost_reference") or data.get("delivery_terms"), "not provided"),
            "detail": ", ".join(evidence_report.get("delivery_assumptions", []) or data.get("delivery_assumptions", []) or []) or "no explicit delivery assumption recorded",
            "append_only": True,
        },
        {
            "step": "vat_treatment",
            "source": _safe_str(evidence_report.get("vat_clarity") or data.get("vat_clarity") or data.get("vat_treatment"), "not stated"),
            "evidence_reference": _safe_str(data.get("vat_reference") or evidence_report.get("quote_reference"), "not provided"),
            "detail": "VAT treatment documented for audit trail",
            "append_only": True,
        },
        {
            "step": "validation",
            "source": "pricing validation",
            "evidence_reference": _safe_str(data.get("validation_reference") or evidence_report.get("quote_reference"), "not provided"),
            "detail": "passed" if validation_report.get("validation_passed", True) else ", ".join(validation_report.get("validation_errors", [])) or "warnings only",
            "append_only": True,
        },
        {
            "step": "final_quoted_amount",
            "source": _safe_str(data.get("currency") or "ZAR", "ZAR"),
            "evidence_reference": _safe_str(data.get("quote_reference") or evidence_report.get("quote_reference"), "not provided"),
            "detail": f"{round(float(final_quoted_amount or 0.0), 2)}",
            "append_only": True,
        },
    ]
    override_notes = data.get("operator_override_notes")
    if isinstance(override_notes, list) and override_notes:
        traceability_chain.append(
            {
                "step": "operator_override",
                "source": "operator notes",
                "evidence_reference": _safe_str(data.get("operator_name") or data.get("operator"), "operator"),
                "detail": "; ".join(str(item) for item in override_notes if str(item).strip()),
                "append_only": True,
            }
        )
    elif data.get("operator_override_notes"):
        traceability_chain.append(
            {
                "step": "operator_override",
                "source": "operator notes",
                "evidence_reference": _safe_str(data.get("operator_name") or data.get("operator"), "operator"),
                "detail": _safe_str(data.get("operator_override_notes"), "override recorded"),
                "append_only": True,
            }
        )

    audit_friendly_summary = (
        f"{_safe_str(evidence_report.get('supplier_name') or data.get('supplier_name'), 'Unknown supplier')} "
        f"quoted {round(float(final_quoted_amount or 0.0), 2)} "
        f"with VAT {_safe_str(evidence_report.get('vat_clarity') or data.get('vat_treatment'), 'not stated')} "
        f"and validation {'passed' if validation_report.get('validation_passed', True) else 'requires review'}."
    )
    return {
        "traceability_chain": traceability_chain,
        "traceability_chain_length": len(traceability_chain),
        "pricing_traceability_summary": {
            "supplier_name": evidence_report.get("supplier_name") or data.get("supplier_name", ""),
            "quote_reference": evidence_report.get("quote_reference") or data.get("quote_reference", ""),
            "final_quoted_amount": round(float(final_quoted_amount or 0.0), 2),
            "audit_friendly_summary": audit_friendly_summary,
            "operator_override_present": bool(data.get("operator_override_notes")),
            "append_only_friendly": True,
            "advisory_only": True,
        },
        "audit_friendly_summary": audit_friendly_summary,
        "advisory_only": True,
    }
