from __future__ import annotations

from typing import Any, Dict

from ._shared import utc_now_iso


def build_pdf_summary_export(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "filename": f"lmcp_strategic_summary_{utc_now_iso().replace(':', '').replace('-', '')}.pdf",
        "content_type": "application/pdf",
        "summary": payload,
    }

