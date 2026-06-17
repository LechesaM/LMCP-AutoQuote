from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.services import supplier_quote_auto_ingestion_service as auto_ingestion
from app.services import supplier_quote_ingestion_service as ingestion
from app.services.supplier_quote_intelligence_service import SupplierQuoteIntelligenceService
from app.services.supplier_quote_ingestion_service import SupplierQuoteIngestionService


def _prepare_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    monthly_quotes_dir = tmp_path / "monthly_quotes"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    monthly_quotes_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MONTHLY_QUOTES_DIR", str(monthly_quotes_dir))
    monkeypatch.setenv("SUPPLIER_QUOTES_SAVE_ROOT", str(monthly_quotes_dir))
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    return monthly_quotes_dir


class _FakeIMAP:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.closed = False

    def login(self, username: str, password: str):
        self.username = username
        self.password = password
        return "OK", [b"logged in"]

    def select(self, mailbox: str = "inbox", readonly: bool = False):
        return "OK", [b"1"]

    def search(self, charset, expression):
        return "OK", [b"1"]

    def fetch(self, msg_id, parts):
        message = EmailMessage()
        message["Subject"] = "Supplier Quote RFQ-500"
        message["From"] = "Alpha Supplies <alpha@example.org>"
        message["Message-ID"] = "<msg-1@example.org>"
        message.set_content("Paper reams 10 Ream R85.00 R850.00\n")
        message.add_attachment(
            b"quote_reference,description,quantity,unit,unit_price,line_total\nALPHA-500,Paper reams,10,Ream,85,850\n",
            maintype="text",
            subtype="csv",
            filename="alpha_quote.csv",
        )
        return "OK", [(b"1 (RFC822)", message.as_bytes())]

    def close(self):
        self.closed = True

    def logout(self):
        return "BYE", [b"logged out"]


class _FakeIMAPBodyPeekFallback(_FakeIMAP):
    def fetch(self, msg_id, parts):
        message = EmailMessage()
        message["Subject"] = "Supplier Quote RFQ-500"
        message["From"] = "Alpha Supplies <alpha@example.org>"
        message["Message-ID"] = "<msg-1@example.org>"
        message.set_content("Paper reams 10 Ream R85.00 R850.00\n")
        message.add_attachment(
            b"quote_reference,description,quantity,unit,unit_price,line_total\nALPHA-500,Paper reams,10,Ream,85,850\n",
            maintype="text",
            subtype="csv",
            filename="alpha_quote.csv",
        )
        if parts == "(RFC822)":
            return "OK", [(b"1 ()", b"")]
        return "OK", [(b"1 (BODY[] {1234})", message.as_bytes())]


class _FakeIMAPInvalidAttachment(_FakeIMAP):
    def fetch(self, msg_id, parts):
        message = EmailMessage()
        message["Subject"] = "Supplier Quote RFQ-600"
        message["From"] = "Alpha Supplies <alpha@example.org>"
        message["Message-ID"] = "<msg-invalid@example.org>"
        message.set_content("Hello supplier team, please see attached quote.")
        message.add_attachment(
            b"<!doctype html><html><body>this is not a pdf</body></html>",
            maintype="application",
            subtype="pdf",
            filename="alpha_quote.pdf",
        )
        return "OK", [(b"1 (RFC822)", message.as_bytes())]


class _FakeIMAPNoiseMessage(_FakeIMAP):
    def fetch(self, msg_id, parts):
        message = EmailMessage()
        message["Subject"] = "Payment Notification from FNB"
        message["From"] = "notifications@fnb.co.za"
        message["Message-ID"] = "<msg-noise@example.org>"
        message.set_content("This is a payment notification and not a supplier quotation.")
        return "OK", [(b"1 (RFC822)", message.as_bytes())]


def test_supplier_quote_ingestion_once_skips_without_credentials(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.delenv("IMAP_USERNAME", raising=False)
    monkeypatch.delenv("IMAP_PASSWORD", raising=False)
    monkeypatch.delenv("EMAIL_USERNAME", raising=False)
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
    monkeypatch.delenv("GMAIL_USERNAME", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

    service = SupplierQuoteIngestionService()
    result = service.ingest_once()

    assert result["status"] == "skipped"
    assert result["success"] is False
    assert "reason" in result


def test_supplier_quote_ingestion_once_probes_and_generates_workspace(monkeypatch, tmp_path: Path) -> None:
    monthly_quotes_dir = _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("IMAP_PASSWORD", "secret")
    monkeypatch.setenv("IMAP_HOST", "imap.example.org")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_SEARCH_QUERY", "RFQ-500")

    monkeypatch.setattr(ingestion.imaplib, "IMAP4_SSL", _FakeIMAP)

    analysis_calls = {}

    def fake_analyze_supplier_quote_folder(*, folder_path, payload=None, margin_percent=25.0, minimum_profit=30000.0):
        analysis_calls["folder_path"] = str(folder_path)
        analysis_calls["payload"] = payload or {}
        return {
            "status": "ok",
            "supplier_quotes": [{"supplier_name": "Alpha Supplies", "quote_reference": "ALPHA-500"}],
            "supplier_quote_comparison": {"recommended_supplier": {"supplier_name": "Alpha Supplies"}},
            "pricing_schedule": {"items": [{"description": "Paper reams"}]},
            "pricing_confidence_summary": {"quote_count": 1},
            "supplier_pricing_quality": {"pricing_confidence_summary": {"quote_count": 1}},
            "pricing_anomalies": [],
            "line_item_comparison": [{"description": "Paper reams"}],
            "artifacts": {"summary_path": str(monthly_quotes_dir / "summary.json")},
            "summary_path": str(monthly_quotes_dir / "summary.json"),
            "extraction_errors": [],
        }

    monkeypatch.setattr(
        "app.services.supplier_quote_intelligence_service.analyze_supplier_quote_folder",
        fake_analyze_supplier_quote_folder,
    )
    monkeypatch.setattr(auto_ingestion, "get_operator_workflow_detail", lambda tender_id: {"tender_id": tender_id, "harvest_enrichment": {"live_rfq": {"items": []}}})
    monkeypatch.setattr(auto_ingestion, "build_review_ready_bundle", lambda detail: {"review_ready": True, "bundle_dir": str(tmp_path / "review_bundle")})
    monkeypatch.setattr(auto_ingestion, "build_submission_package", lambda detail: {"submission_ready": True, "package_dir": str(tmp_path / "submission_package")})
    monkeypatch.setattr(auto_ingestion, "append_audit_event", lambda **kwargs: {"id": "audit-1", **kwargs})

    service = SupplierQuoteIngestionService()
    result = service.ingest_once()

    assert result["success"] is True
    assert result["status"] == "ok"
    assert result["processed"] == 1
    assert result["saved_attachments"] == 1
    assert result["folders_updated"]
    assert Path(result["workspace"]).exists()
    assert result["supplier_quote_comparison"]["recommended_supplier"]["supplier_name"] == "Alpha Supplies"
    assert result["supplier_quotes"][0]["supplier_name"] == "Alpha Supplies"
    assert result["imap_probe"]["status"] == "ok"
    assert result["submission_ready"] is True
    assert analysis_calls["folder_path"] == result["workspace"]


def test_supplier_quote_ingestion_once_supports_supplier_quote_aliases_and_attachment_parsing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monthly_quotes_dir = _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PASSWORD", "secret")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_HOST", "imap.example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PORT", "993")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_SEARCH_QUERY", "RFQ-500")

    monkeypatch.setattr(ingestion.imaplib, "IMAP4_SSL", _FakeIMAP)

    def real_analyze_supplier_quote_folder(*, folder_path, payload=None, margin_percent=25.0, minimum_profit=30000.0):
        return SupplierQuoteIntelligenceService.analyze_folder(
            folder_path=folder_path,
            payload=payload or {},
            margin_percent=margin_percent,
            minimum_profit=minimum_profit,
        )

    monkeypatch.setattr(
        "app.services.supplier_quote_intelligence_service.analyze_supplier_quote_folder",
        real_analyze_supplier_quote_folder,
    )
    monkeypatch.setattr(
        auto_ingestion,
        "scan_quote_folders",
        lambda *, root_path, force=True, payload=None: {
            "status": "ok",
            "processed": [{"review_ready": True, "submission_ready": True}],
            "errors": [],
        },
    )

    service = SupplierQuoteIngestionService()
    result = service.ingest_once()

    assert service.is_configured() is True
    assert service.credential_source == "SUPPLIER_QUOTES_IMAP_USERNAME/SUPPLIER_QUOTES_IMAP_PASSWORD"
    assert result["success"] is True
    assert result["status"] == "ok"
    assert result["processed"] == 1
    assert result["saved_attachments"] == 1
    assert result["imap_probe"]["status"] == "ok"
    assert result["submission_ready"] is True
    assert result["review_ready"] is True
    assert result["supplier_quote_analysis"]["status"] == "ok"
    assert any(
        quote.get("source_type") == "csv" for quote in result["supplier_quote_analysis"]["supplier_quotes"]
    )
    assert result["supplier_quote_analysis"]["pricing_schedule"]["items"]
    assert Path(result["workspace"]).exists()
    assert result["workspace"].startswith(str(monthly_quotes_dir))


def test_supplier_quote_ingestion_once_honours_explicit_search_query(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PASSWORD", "secret")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_HOST", "imap.example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PORT", "993")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_SEARCH_QUERY", "request for quotation")

    monkeypatch.setattr(ingestion.imaplib, "IMAP4_SSL", _FakeIMAP)
    monkeypatch.setattr(
        "app.services.supplier_quote_intelligence_service.analyze_supplier_quote_folder",
        lambda *, folder_path, payload=None, margin_percent=25.0, minimum_profit=30000.0: {
            "status": "ok",
            "supplier_quotes": [{"supplier_name": "Alpha Supplies", "quote_reference": "ALPHA-500"}],
            "supplier_quote_comparison": {"recommended_supplier": {"supplier_name": "Alpha Supplies"}},
            "pricing_schedule": {"items": [{"description": "Paper reams"}]},
            "pricing_confidence_summary": {"quote_count": 1},
            "supplier_pricing_quality": {"pricing_confidence_summary": {"quote_count": 1}},
            "pricing_anomalies": [],
            "line_item_comparison": [{"description": "Paper reams"}],
            "artifacts": {"summary_path": str(tmp_path / "summary.json")},
            "summary_path": str(tmp_path / "summary.json"),
            "extraction_errors": [],
        },
    )
    monkeypatch.setattr(auto_ingestion, "scan_quote_folders", lambda *, root_path, force=True, payload=None: {"status": "ok", "processed": [{"review_ready": True, "submission_ready": True}], "errors": []})
    monkeypatch.setattr(auto_ingestion, "get_operator_workflow_detail", lambda tender_id: {"tender_id": tender_id, "harvest_enrichment": {"live_rfq": {"items": []}}})
    monkeypatch.setattr(auto_ingestion, "build_review_ready_bundle", lambda detail: {"review_ready": True, "bundle_dir": str(tmp_path / "review_bundle")})
    monkeypatch.setattr(auto_ingestion, "build_submission_package", lambda detail: {"submission_ready": True, "package_dir": str(tmp_path / "submission_package")})
    monkeypatch.setattr(auto_ingestion, "append_audit_event", lambda **kwargs: {"id": "audit-1", **kwargs})

    service = SupplierQuoteIngestionService()
    result = service.ingest_once(search_query="RFQ-500", max_messages=5)

    assert result["success"] is True
    assert result["imap_search_query"] == "RFQ-500"
    assert result["processed"] == 1
    assert result["submission_ready"] is True


def test_supplier_quote_ingestion_once_falls_back_to_body_peek_when_rfc822_is_empty(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PASSWORD", "secret")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_HOST", "imap.example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PORT", "993")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_SEARCH_QUERY", "RFQ-500")

    monkeypatch.setattr(ingestion.imaplib, "IMAP4_SSL", _FakeIMAPBodyPeekFallback)

    monkeypatch.setattr(
        "app.services.supplier_quote_intelligence_service.analyze_supplier_quote_folder",
        lambda *, folder_path, payload=None, margin_percent=25.0, minimum_profit=30000.0: {
            "status": "ok",
            "supplier_quotes": [{"supplier_name": "Alpha Supplies", "quote_reference": "ALPHA-500"}],
            "supplier_quote_comparison": {"recommended_supplier": {"supplier_name": "Alpha Supplies"}},
            "pricing_schedule": {"items": [{"description": "Paper reams"}]},
            "pricing_confidence_summary": {"quote_count": 1},
            "supplier_pricing_quality": {"pricing_confidence_summary": {"quote_count": 1}},
            "pricing_anomalies": [],
            "line_item_comparison": [{"description": "Paper reams"}],
            "artifacts": {"summary_path": str(tmp_path / "summary.json")},
            "summary_path": str(tmp_path / "summary.json"),
            "extraction_errors": [],
        },
    )
    monkeypatch.setattr(auto_ingestion, "scan_quote_folders", lambda *, root_path, force=True, payload=None: {"status": "ok", "processed": [{"review_ready": True, "submission_ready": True}], "errors": []})
    monkeypatch.setattr(auto_ingestion, "get_operator_workflow_detail", lambda tender_id: {"tender_id": tender_id, "harvest_enrichment": {"live_rfq": {"items": []}}})
    monkeypatch.setattr(auto_ingestion, "build_review_ready_bundle", lambda detail: {"review_ready": True, "bundle_dir": str(tmp_path / "review_bundle")})
    monkeypatch.setattr(auto_ingestion, "build_submission_package", lambda detail: {"submission_ready": True, "package_dir": str(tmp_path / "submission_package")})
    monkeypatch.setattr(auto_ingestion, "append_audit_event", lambda **kwargs: {"id": "audit-1", **kwargs})

    service = SupplierQuoteIngestionService()
    result = service.ingest_once()

    assert result["success"] is True
    assert result["status"] == "ok"
    assert result["processed"] == 1
    assert result["saved_attachments"] == 1
    assert result["imap_probe"]["status"] == "ok"
    assert result["supplier_quote_ingestion"]["matched_count"] == 1
    assert Path(result["workspace"]).exists()


def test_supplier_quote_ingestion_marks_mislabeled_pdf_html_attachment_invalid(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PASSWORD", "secret")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_HOST", "imap.example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PORT", "993")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_SEARCH_QUERY", "RFQ-600")

    monkeypatch.setattr(ingestion.imaplib, "IMAP4_SSL", _FakeIMAPInvalidAttachment)
    monkeypatch.setattr(
        auto_ingestion,
        "scan_quote_folders",
        lambda *, root_path, force=True, payload=None: {"status": "ok", "processed": [{"review_ready": True, "submission_ready": True}], "errors": []},
    )
    monkeypatch.setattr(auto_ingestion, "get_operator_workflow_detail", lambda tender_id: {"tender_id": tender_id, "harvest_enrichment": {"live_rfq": {"items": []}}})
    monkeypatch.setattr(auto_ingestion, "build_review_ready_bundle", lambda detail: {"review_ready": True, "bundle_dir": str(tmp_path / "review_bundle")})
    monkeypatch.setattr(auto_ingestion, "build_submission_package", lambda detail: {"submission_ready": True, "package_dir": str(tmp_path / "submission_package")})
    monkeypatch.setattr(auto_ingestion, "append_audit_event", lambda **kwargs: {"id": "audit-1", **kwargs})

    service = SupplierQuoteIngestionService()
    result = service.ingest_once()

    assert result["success"] is True
    assert result["status"] == "ok"
    assert result["processed"] == 1
    assert result["saved_attachments"] == 1
    assert result["warnings"]
    assert any("mislabeled as PDF" in warning for warning in result["warnings"])
    assert any(str(path).endswith(".invalid_attachment_type.html") for path in result["saved_files"])
    assert any("skipped from parsing" in warning for warning in result["supplier_quote_ingestion"]["warnings"])
    assert any("mislabeled as PDF" in warning for warning in result["supplier_quote_analysis"]["warnings"])


def test_supplier_quote_ingestion_skips_obvious_noise_messages(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PASSWORD", "secret")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_HOST", "imap.example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PORT", "993")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_SEARCH_QUERY", "ALL")

    monkeypatch.setattr(ingestion.imaplib, "IMAP4_SSL", _FakeIMAPNoiseMessage)

    service = SupplierQuoteIngestionService()
    result = service.ingest_once()

    assert result["success"] is True
    assert result["status"] == "empty"
    assert result["processed"] == 0
    assert result["reason"] == "No new matching supplier quote messages found"


def test_supplier_quote_status_route_includes_imap_probe(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("IMAP_PASSWORD", "secret")

    monkeypatch.setattr(
        SupplierQuoteIngestionService,
        "_probe_imap_connection",
        lambda self, username, password: {
            "status": "ok",
            "message": "IMAP connection established",
            "host": self.imap_host,
            "port": self.imap_port,
            "mailbox": "inbox",
            "message_count": 2,
        },
    )

    from app.api.supplier_quote_status_routes import supplier_quotes_status

    status = supplier_quotes_status()

    assert status["configured"] is True
    assert status["imap_port"] == 993
    assert status["imap_probe"]["status"] == "ok"
    assert status["imap_probe"]["message_count"] == 2
