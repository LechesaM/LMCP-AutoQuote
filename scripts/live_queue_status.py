from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_daily_pilot_loop import _clean, _completed_tenders, _queue_selection_summary


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


def build_live_queue_status(queue_file: Path) -> Dict[str, Any]:
    queue = _read_json(queue_file)
    completed = _completed_tenders()
    selection_summary = _queue_selection_summary(queue, completed=completed)
    items = [item for item in queue.get("items", []) if isinstance(item, dict)]
    return {
        "queue_file": str(queue_file),
        "queue_status": _clean(queue.get("status") or "unknown"),
        "queue_updated_at": _clean(queue.get("updated_at")),
        "queue_count": int(queue.get("count", len(items)) or len(items)),
        "items_in_file": len(items),
        "completed_tenders": len(completed),
        "fresh_runnable_candidates": int(selection_summary.get("fresh_runnable_candidates", 0) or 0),
        "repeat_runnable_candidates": int(selection_summary.get("repeat_runnable_candidates", 0) or 0),
        "unavailable_candidates": int(selection_summary.get("unavailable_candidates", 0) or 0),
        "selection_summary": selection_summary,
        "queue_empty": len(items) == 0,
    }


def _print_summary(payload: Dict[str, Any]) -> None:
    print(f"queue file: {payload.get('queue_file')}")
    print(f"queue status: {payload.get('queue_status')}")
    print(f"queue count: {payload.get('queue_count', 0)}")
    print(f"items in file: {payload.get('items_in_file', 0)}")
    print(f"fresh runnable candidates: {payload.get('fresh_runnable_candidates', 0)}")
    print(f"repeat runnable candidates: {payload.get('repeat_runnable_candidates', 0)}")
    print(f"unavailable candidates: {payload.get('unavailable_candidates', 0)}")
    print(f"queue empty: {str(bool(payload.get('queue_empty', False))).lower()}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Show the live RFQ queue status.")
    parser.add_argument("--queue-file", type=Path, default=LIVE_QUEUE_PATH, help="Queue file to inspect.")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    parser.add_argument("--fail-if-empty", action="store_true", help="Exit nonzero when the queue has no items.")
    args = parser.parse_args(argv)

    payload = build_live_queue_status(args.queue_file)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_summary(payload)
    if args.fail_if_empty and bool(payload.get("queue_empty", False)):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
