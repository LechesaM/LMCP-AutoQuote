from __future__ import annotations

import json
import re
from typing import Any, Dict

from .csv_exporter import build_csv_export
from .pdf_summary_exporter import build_pdf_summary_export
from .strategic_reporting import build_strategic_report
from ._shared import now_iso


_SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "cookie"}
_SENSITIVE_ASSIGNMENT = re.compile(r"(?i)\b(password|secret|token|authorization|cookie)\b\s*[:=]\s*([^\s,;\"']+)")
_SENSITIVE_KEYWORD = re.compile(r"(?i)\b(password|secret|token|authorization|cookie)\b")


def _sanitize(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {child_key: _sanitize(item, child_key) for child_key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item, key) for item in value]
    if key and str(key).lower() in _SENSITIVE_KEYS:
        return "[redacted]"
    text = str(value)
    text = _SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _SENSITIVE_KEYWORD.sub("[redacted]", text)
    return text if isinstance(value, str) else value


def build_report_export_bundle(limit: int = 100) -> Dict[str, Any]:
    report = build_strategic_report(limit=limit)
    safe_report = _sanitize(report)
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": safe_report.get("data_source", "fallback"),
        "report": safe_report,
        "csv": build_csv_export(safe_report),
        "pdf_summary": build_pdf_summary_export(safe_report),
    }
