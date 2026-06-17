from __future__ import annotations

import json
from pathlib import Path

from app.scripts import run_source_by_source_live_smoke as smoke_script


def test_source_by_source_live_smoke_runs_one_source_at_a_time(tmp_path, monkeypatch, capsys) -> None:
    source_file = tmp_path / "sources.json"
    source_file.write_text(
        json.dumps(
            [
                {"name": "Alpha Portal", "url": "https://alpha.example.com", "type": "web"},
                {"name": "Beta Portal", "url": "https://beta.example.com", "type": "web"},
            ]
        ),
        encoding="utf-8",
    )

    captured_source_files: list[Path] = []

    def fake_run_national_tender_radar(**kwargs):
        path = Path(kwargs["source_file"])
        captured_source_files.append(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1
        return {
            "status": "ok",
            "harvested_total": 1,
            "eligible_total": 1,
            "quote_ready_total": 0,
            "source_health_overview": {"status": "ok"},
            "browser_available": False,
            "source_timeout_seconds": kwargs.get("source_timeout_seconds"),
            "playwright_timeout_ms": kwargs.get("playwright_timeout_ms"),
        }

    monkeypatch.setattr(smoke_script, "run_national_tender_radar", fake_run_national_tender_radar)

    exit_code = smoke_script.main(
        [
            "--source-file",
            str(source_file),
            "--limit",
            "2",
            "--runtime-dir",
            str(tmp_path),
            "--source-timeout-seconds",
            "3",
            "--playwright-timeout-ms",
            "5000",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["source_count"] == 2
    assert len(captured_source_files) == 2
    assert all(path.parent == tmp_path for path in captured_source_files)
