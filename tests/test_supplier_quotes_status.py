from __future__ import annotations

import asyncio
import hashlib
import json
import smtplib
from pathlib import Path
from typing import Any, Dict, List

import imaplib


async def _asgi_get(app: Any, path: str) -> Dict[str, Any]:
    messages: List[Dict[str, Any]] = []
    sent_request = False
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [(b"host", b"testserver"), (b"accept", b"application/json")],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
        "root_path": "",
    }

    async def receive() -> Dict[str, Any]:
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: Dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)
    status = 0
    headers: Dict[str, str] = {}
    body = b""
    for message in messages:
        if message["type"] == "http.response.start":
            status = int(message["status"])
            headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in message.get("headers", [])}
        elif message["type"] == "http.response.body":
            body += message.get("body", b"")
    return {"status": status, "headers": headers, "body": body}


def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _block_external(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("external connection must not be attempted by supplier quote status")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", blocked)
    monkeypatch.setattr(smtplib, "SMTP", blocked)
    monkeypatch.setattr(smtplib, "SMTP_SSL", blocked)


def test_supplier_quotes_status_get_returns_json_disabled_without_enablement(monkeypatch):
    _block_external(monkeypatch)
    monkeypatch.delenv("LMCP_SUPPLIER_QUOTE_INGESTION_ENABLED", raising=False)

    from app.main import app

    response = asyncio.run(_asgi_get(app, "/supplier-quotes/status"))
    payload = json.loads(response["body"].decode("utf-8"))

    assert response["status"] == 200
    assert response["headers"]["content-type"].startswith("application/json")
    assert payload["enabled"] is False
    assert payload["read_only"] is True
    assert payload["polling_started"] is False
    assert payload["external_connection_attempted"] is False
    assert payload["enablement_env"] == "LMCP_SUPPLIER_QUOTE_INGESTION_ENABLED"


def test_supplier_quotes_status_false_when_configured_false(monkeypatch):
    _block_external(monkeypatch)
    monkeypatch.setenv("LMCP_SUPPLIER_QUOTE_INGESTION_ENABLED", "false")

    from app.main import app

    response = asyncio.run(_asgi_get(app, "/supplier-quotes/status"))
    payload = json.loads(response["body"].decode("utf-8"))

    assert response["status"] == 200
    assert payload["enabled"] is False
    assert payload["external_connection_attempted"] is False


def test_supplier_quotes_status_does_not_call_run_once_or_mutate_runtime(monkeypatch):
    _block_external(monkeypatch)
    protected = [
        "runtime/live_rfqs.json",
        "runtime/rfq_lifecycle/rfqs.json",
    ]
    before = {path: _sha256(path) for path in protected}

    from app.main import app
    from app.services.supplier_quote_ingestion_service import SupplierQuoteIngestionService

    def forbidden_ingest_once(self):
        raise AssertionError("/supplier-quotes/status must not invoke ingest_once")

    monkeypatch.setattr(SupplierQuoteIngestionService, "ingest_once", forbidden_ingest_once)

    response = asyncio.run(_asgi_get(app, "/supplier-quotes/status"))
    payload = json.loads(response["body"].decode("utf-8"))
    after = {path: _sha256(path) for path in protected}

    assert response["status"] == 200
    assert payload["enabled"] is False
    assert before == after
