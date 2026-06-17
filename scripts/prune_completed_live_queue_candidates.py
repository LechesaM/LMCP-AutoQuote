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

from scripts.run_daily_pilot_loop import _clean, _completed_tenders, _candidate_id


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


def prune_completed_live_queue_candidates(queue_file: Path) -> Dict[str, Any]:
    queue = _read_json(queue_file)
    items = [item for item in queue.get("items", []) if isinstance(item, dict)]
    completed = _completed_tenders()
    kept_items: List[Dict[str, Any]] = []
    pruned_items: List[Dict[str, Any]] = []
    for item in items:
        tender_id = _candidate_id(item)
        if tender_id and tender_id in completed:
            pruned_items.append(item)
            continue
        kept_items.append(item)

    queue["items"] = kept_items
    queue["count"] = len(kept_items)
    queue["updated_at"] = queue.get("updated_at") or ""
    queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "queue_file": str(queue_file),
        "completed_tenders": len(completed),
        "kept_count": len(kept_items),
        "pruned_count": len(pruned_items),
        "pruned_tender_ids": [_clean(_candidate_id(item)) for item in pruned_items if _clean(_candidate_id(item))],
        "kept_tender_ids": [_clean(_candidate_id(item)) for item in kept_items if _clean(_candidate_id(item))],
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prune completed tenders from the live RFQ queue.")
    parser.add_argument("--queue-file", type=Path, default=LIVE_QUEUE_PATH, help="Queue file to prune.")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    args = parser.parse_args(argv)

    report = prune_completed_live_queue_candidates(args.queue_file)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"queue file: {report['queue_file']}")
        print(f"completed tenders: {report['completed_tenders']}")
        print(f"pruned count: {report['pruned_count']}")
        print(f"kept count: {report['kept_count']}")
        if report["pruned_tender_ids"]:
            print("pruned tender ids:")
            for tender_id in report["pruned_tender_ids"]:
                print(f"- {tender_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
