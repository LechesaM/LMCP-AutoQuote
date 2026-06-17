from __future__ import annotations

import json
from pathlib import Path

from scripts.normalize_live_queue_candidates import normalize_live_queue_candidates


def test_normalize_live_queue_candidates_fills_missing_ids(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    queue_file = runtime_root / "live_rfqs.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps(
            {
                "status": "ok",
                "count": 2,
                "items": [
                    {"title": "RFQ One", "rfq_number": "", "reference": "", "buyer_rfq_number": ""},
                    {"rfq_id": "RFQ-2", "title": "RFQ Two", "rfq_number": "RFQ-2"},
                ],
            }
        ),
        encoding="utf-8",
    )

    from scripts import normalize_live_queue_candidates as module

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", queue_file)

    report = normalize_live_queue_candidates(queue_file)

    assert report["normalized_count"] == 1
    assert report["skipped_count"] == 0
    saved = json.loads(queue_file.read_text(encoding="utf-8"))
    assert saved["count"] == 2
    assert saved["items"][0]["rfq_id"] == "RFQ One"
    assert saved["items"][0]["reference"] == "RFQ One"
    assert saved["items"][0]["buyer_rfq_number"] == "RFQ One"
    assert saved["items"][0]["document_number"] == "RFQ One"

