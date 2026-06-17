from __future__ import annotations

from pathlib import Path

from app.api.supplier_quote_status_routes import (
    supplier_quotes_auto_ingest_status,
    supplier_quotes_intelligence_status,
    supplier_quotes_status,
)


def test_supplier_quote_status_routes_return_service_snapshot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LMCP_MONTHLY_QUOTES_DIR", str(tmp_path / "monthly_quotes"))
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("SUPPLIER_QUOTES_IMAP_PASSWORD", "secret")
    monkeypatch.setattr(
        "app.api.supplier_quote_status_routes.SupplierQuoteIngestionService._probe_imap_connection",
        lambda self, username, password: {
            "status": "ok",
            "message": "IMAP connection established",
            "host": self.imap_host,
            "port": self.imap_port,
            "mailbox": "inbox",
            "message_count": 0,
        },
    )

    status = supplier_quotes_status()
    auto_ingest_status = supplier_quotes_auto_ingest_status()
    intelligence_status = supplier_quotes_intelligence_status()

    assert status["imap_host"]
    assert status["imap_port"] == 993
    assert status["email_address"] == "quotes@example.org"
    assert status["save_root"]
    assert status["configured"] is True
    assert status["credential_source"] == "SUPPLIER_QUOTES_IMAP_USERNAME/SUPPLIER_QUOTES_IMAP_PASSWORD"
    assert status["imap_probe"]["status"] == "ok"
    assert status["live_mailbox_source"]["configured"] is True
    assert status["live_mailbox_source"]["ready"] is True
    assert status["live_mailbox_source"]["status"] == "ready"
    assert "SUPPLIER_QUOTES_IMAP_USERNAME" in status["live_mailbox_source"]["requirements"]

    assert auto_ingest_status["status"] == "ok"
    assert "watch_status" in auto_ingest_status

    assert intelligence_status["status"] in {"ok", "empty"}


def test_supplier_quote_status_routes_surface_missing_credentials(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LMCP_MONTHLY_QUOTES_DIR", str(tmp_path / "monthly_quotes"))
    monkeypatch.delenv("SUPPLIER_QUOTES_IMAP_USERNAME", raising=False)
    monkeypatch.delenv("SUPPLIER_QUOTES_IMAP_PASSWORD", raising=False)

    status = supplier_quotes_status()

    assert status["configured"] is False
    assert status["enabled"] is False
    assert status["live_mailbox_source"]["configured"] is False
    assert status["live_mailbox_source"]["ready"] is False
    assert status["live_mailbox_source"]["status"] == "not_ready"
    assert "not configured" in status["live_mailbox_source"]["message"].lower()
