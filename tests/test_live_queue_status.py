from __future__ import annotations

import json
from pathlib import Path

from scripts.live_queue_status import build_live_queue_status
from scripts.live_queue_status import main


def test_live_queue_status_reports_empty_queue(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    queue_file = runtime_root / "live_rfqs.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps({"status": "ok", "count": 0, "items": []}), encoding="utf-8")

    from scripts import live_queue_status as module

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", queue_file)
    monkeypatch.setattr(module, "_completed_tenders", lambda: set())
    monkeypatch.setattr(module, "_queue_selection_summary", lambda queue, completed=None: {
        "queue_items": 0,
        "fresh_runnable_candidates": 0,
        "repeat_runnable_candidates": 0,
        "unavailable_candidates": 0,
        "completed_tenders": 0,
    })

    report = build_live_queue_status(queue_file)

    assert report["queue_empty"] is True
    assert report["queue_count"] == 0
    assert report["fresh_runnable_candidates"] == 0
    assert report["repeat_runnable_candidates"] == 0


def test_live_queue_status_reports_counts(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    queue_file = runtime_root / "live_rfqs.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps(
            {
                "status": "ok",
                "count": 2,
                "items": [
                    {"rfq_id": "LIVE-1", "status": "Quote Ready"},
                    {"rfq_id": "LIVE-2", "status": "Review Required"},
                ],
            }
        ),
        encoding="utf-8",
    )

    from scripts import live_queue_status as module

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", queue_file)
    monkeypatch.setattr(module, "_completed_tenders", lambda: {"LIVE-1"})
    monkeypatch.setattr(module, "_queue_selection_summary", lambda queue, completed=None: {
        "queue_items": 2,
        "fresh_runnable_candidates": 1,
        "repeat_runnable_candidates": 1,
        "unavailable_candidates": 0,
        "completed_tenders": 1,
    })

    report = build_live_queue_status(queue_file)

    assert report["queue_empty"] is False
    assert report["queue_count"] == 2
    assert report["fresh_runnable_candidates"] == 1
    assert report["repeat_runnable_candidates"] == 1


def test_live_queue_status_fail_if_empty_returns_nonzero(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    queue_file = runtime_root / "live_rfqs.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps({"status": "ok", "count": 0, "items": []}), encoding="utf-8")

    from scripts import live_queue_status as module

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", queue_file)
    monkeypatch.setattr(module, "_completed_tenders", lambda: set())
    monkeypatch.setattr(module, "_queue_selection_summary", lambda queue, completed=None: {
        "queue_items": 0,
        "fresh_runnable_candidates": 0,
        "repeat_runnable_candidates": 0,
        "unavailable_candidates": 0,
        "completed_tenders": 0,
    })

    assert main(["--queue-file", str(queue_file), "--fail-if-empty"]) == 2
