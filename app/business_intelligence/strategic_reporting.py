from __future__ import annotations

from typing import Any, Dict

from ._shared import base_report, utc_now_iso


def build_strategic_report(limit: int = 25) -> Dict[str, Any]:
    report = base_report(limit=limit)
    summary = report["summary"]
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "data_source": report["data_source"],
        "executive_summary": summary,
        "weekly_operations": report,
        "export_ready": True,
        "recommendation": "continue supervised production operations",
    }

