from __future__ import annotations

from typing import Any, Dict

from ._shared import redact_sensitive, utc_now_iso
from .strategic_reporting import build_strategic_report


def build_report_export_bundle(limit: int = 100) -> Dict[str, Any]:
    report = build_strategic_report(limit=limit)
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "bundle": redact_sensitive(report),
        "export_ready": True,
    }

