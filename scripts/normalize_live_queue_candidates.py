from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_daily_pilot_loop import _candidate_id, _clean


RUNTIME_ROOT = PROJECT_ROOT / "runtime"
LIVE_QUEUE_PATH = RUNTIME_ROOT / "live_rfqs.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def normalize_live_queue_candidates(queue_file: Path) -> Dict[str, Any]:
    queue = _read_json(queue_file)
    items = [item for item in queue.get("items", []) if isinstance(item, dict)]
    normalized_items: List[Dict[str, Any]] = []
    normalized_count = 0
    skipped_count = 0

    for item in items:
        normalized = dict(item)
        candidate_id = _clean(_candidate_id(normalized))
        if not candidate_id:
            skipped_count += 1
            continue
        if not _clean(normalized.get("rfq_id")):
            normalized["rfq_id"] = candidate_id
            normalized_count += 1
        for key in ("external_id", "reference", "buyer_rfq_number", "rfq_number", "document_number"):
            if not _clean(normalized.get(key)):
                normalized[key] = candidate_id
        normalized_items.append(normalized)

    queue["items"] = normalized_items
    queue["count"] = len(normalized_items)
    queue["updated_at"] = queue.get("updated_at") or ""
    queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "queue_file": str(queue_file),
        "normalized_count": normalized_count,
        "skipped_count": skipped_count,
        "kept_count": len(normalized_items),
        "candidate_ids": [_clean(_candidate_id(item)) for item in normalized_items if _clean(_candidate_id(item))],
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize live RFQ queue items with stable identifiers.")
    parser.add_argument("--queue-file", type=Path, default=LIVE_QUEUE_PATH, help="Queue file to normalize.")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    args = parser.parse_args(argv)

    report = normalize_live_queue_candidates(args.queue_file)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"queue file: {report['queue_file']}")
        print(f"normalized count: {report['normalized_count']}")
        print(f"skipped count: {report['skipped_count']}")
        print(f"kept count: {report['kept_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
