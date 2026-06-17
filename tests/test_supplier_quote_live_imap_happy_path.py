from __future__ import annotations

import importlib.util
from pathlib import Path

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths


def _load_live_imap_module():
    module_path = Path("/Users/cash/Documents/scripts/supplier_quote_live_imap_happy_path.py")
    spec = importlib.util.spec_from_file_location("supplier_quote_live_imap_happy_path", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare_runtime(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    monthly_quotes_dir = tmp_path / "monthly_quotes"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    monthly_quotes_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MONTHLY_QUOTES_DIR", str(monthly_quotes_dir))
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()


def test_live_imap_stage_skips_without_credentials(monkeypatch, tmp_path: Path, capsys) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.delenv("IMAP_USERNAME", raising=False)
    monkeypatch.delenv("IMAP_PASSWORD", raising=False)
    monkeypatch.delenv("EMAIL_USERNAME", raising=False)
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
    monkeypatch.delenv("GMAIL_USERNAME", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

    live_imap = _load_live_imap_module()
    exit_code = live_imap.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "skipped"' in output
    assert "IMAP credentials not configured" in output


def test_live_imap_stage_reports_success_when_service_succeeds(monkeypatch, tmp_path: Path, capsys) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("IMAP_PASSWORD", "secret")

    class _Service:
        enabled = True
        imap_host = "imap.example.org"
        imap_port = 993

        def is_configured(self):
            return True

        def ingest_once(self):
            workspace = tmp_path / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            return {
                "status": "ok",
                "success": True,
                "processed": 1,
                "saved_attachments": 2,
                "workspace": str(workspace),
                "reason": "done",
                "imap_probe": {"status": "ok", "message": "IMAP connection established", "message_count": 2},
                "submission_ready": True,
                "review_ready": True,
            }

    live_imap = _load_live_imap_module()
    monkeypatch.setattr(live_imap, "SupplierQuoteIngestionService", _Service)

    exit_code = live_imap.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "ok"' in output
    assert '"saved_attachments": 2' in output
    assert '"submission_ready": true' in output


def test_live_imap_stage_treats_empty_probe_success_as_pass(monkeypatch, tmp_path: Path, capsys) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_USERNAME", "quotes@example.org")
    monkeypatch.setenv("IMAP_PASSWORD", "secret")

    class _Service:
        enabled = True
        imap_host = "imap.example.org"
        imap_port = 993

        def is_configured(self):
            return True

        def ingest_once(self):
            return {
                "status": "empty",
                "success": True,
                "processed": 0,
                "saved_attachments": 0,
                "workspace": None,
                "reason": "No new matching supplier quote messages found",
                "imap_probe": {"status": "ok", "message": "IMAP connection established", "message_count": 2},
                "submission_ready": False,
                "review_ready": False,
            }

    live_imap = _load_live_imap_module()
    monkeypatch.setattr(live_imap, "SupplierQuoteIngestionService", _Service)

    exit_code = live_imap.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "empty"' in output
    assert '"treat_as_pass": true' in output
    assert '"pass_reason": "IMAP probe succeeded and no new matching supplier quote messages were available."' in output
