from __future__ import annotations

import json

from app.business_intelligence.report_exporter import build_report_export_bundle
from app.business_intelligence.pdf_summary_exporter import build_pdf_summary_export
from app.business_intelligence.csv_exporter import build_csv_export
from app.business_intelligence.strategic_reporting import build_strategic_report


def test_strategic_reports_json_safe() -> None:
    payload = build_strategic_report(limit=25)
    json.dumps(payload, default=str)
    assert payload["export_ready"] is True


def test_exports_redact_secrets(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.business_intelligence.report_exporter.build_strategic_report",
        lambda limit=100: {
            "status": "ok",
            "generated_at": "2026-05-20T00:00:00+00:00",
            "data_source": "runtime",
            "executive_summary": {"rfqs_harvested": 1},
            "secret": "token=abc123 password=xyz",
            "nested": {"password": "super-secret"},
        },
    )
    bundle = build_report_export_bundle(limit=10)
    payload_text = json.dumps(bundle, default=str)
    assert "abc123" not in payload_text
    assert "super-secret" not in payload_text
    assert "password" not in payload_text.lower() or "[redacted]" in payload_text


def test_pdf_summary_generated_safely() -> None:
    payload = build_pdf_summary_export({"executive_summary": {"rfqs_harvested": 5}, "data_source": "runtime"})
    json.dumps(payload, default=str)
    assert payload["filename"].endswith(".pdf")


def test_csv_export_generated_safely() -> None:
    payload = build_csv_export({"executive_summary": {"rfqs_harvested": 5}, "data_source": "runtime"})
    json.dumps(payload, default=str)
    assert payload["filename"].endswith(".csv")

