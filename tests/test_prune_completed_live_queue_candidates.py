from __future__ import annotations

import json
from pathlib import Path

from scripts.prune_completed_live_queue_candidates import prune_completed_live_queue_candidates


def test_prune_completed_live_queue_candidates_removes_completed_items(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    manual_root.mkdir(parents=True, exist_ok=True)
    queue_file = runtime_root / "live_rfqs.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps(
            {
                "status": "ok",
                "count": 3,
                "items": [
                    {"rfq_id": "COMPLETE-1", "title": "Complete 1", "status": "Quote Ready"},
                    {"rfq_id": "COMPLETE-2", "title": "Complete 2", "status": "Quote Ready"},
                    {"rfq_id": "REMAIN-1", "title": "Remain 1", "status": "Review Required"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (manual_root / "pilot_runs.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"tender_id": "COMPLETE-1", "outcome": "completed", "status": "recorded"}),
                json.dumps({"tender_id": "COMPLETE-2", "outcome": "completed", "status": "recorded"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    from scripts import prune_completed_live_queue_candidates as module

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", queue_file)
    monkeypatch.setattr(module, "_completed_tenders", lambda: {"COMPLETE-1", "COMPLETE-2"})

    report = prune_completed_live_queue_candidates(queue_file)

    assert report["pruned_count"] == 2
    assert report["kept_count"] == 1
    saved = json.loads(queue_file.read_text(encoding="utf-8"))
    assert saved["count"] == 1
    assert [item["rfq_id"] for item in saved["items"]] == ["REMAIN-1"]
