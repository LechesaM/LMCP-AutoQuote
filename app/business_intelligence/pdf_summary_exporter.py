from __future__ import annotations

from typing import Any, Dict, List

from ._shared import now_iso


def build_pdf_summary_export(report: Dict[str, Any]) -> Dict[str, Any]:
    executive = report.get("executive_summary", {})
    lines = [
        "LMCP Operational Business Intelligence Summary",
        f"RFQs harvested: {executive.get('rfqs_harvested', 0)}",
        f"RFQs qualified: {executive.get('rfqs_qualified', 0)}",
        f"RFQs reviewed: {executive.get('rfqs_reviewed', 0)}",
        f"Estimated profitability: {executive.get('estimated_profitability', 0)}",
        f"Operator throughput: {executive.get('operator_throughput', 0)}",
        f"Governance incidents: {executive.get('governance_incidents', 0)}",
        f"Source reliability: {executive.get('source_reliability', 0)}",
        f"SLA health: {executive.get('sla_health', 'healthy')}",
        "Manual approval, review_ready and proof capture remain mandatory.",
    ]
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": report.get("data_source", "fallback"),
        "filename": "strategic_report_summary.pdf",
        "summary_text": "\n".join(lines),
        "line_count": len(lines),
    }

