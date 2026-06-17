#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.celery_app import celery_app


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _inspect_ready(queue_name: str, timeout_seconds: float) -> Dict[str, Any]:
    try:
        inspector = celery_app.control.inspect(timeout=float(timeout_seconds))
        ping = inspector.ping() or {}
        active_queues = inspector.active_queues() or {}
    except Exception as exc:
        return {
            "status": "unhealthy",
            "ready": False,
            "queue_name": queue_name,
            "error": str(exc),
            "checked_at": time.time(),
            "online_workers": [],
            "queue_workers": [],
        }

    online_workers = sorted(ping.keys())
    queue_workers = sorted(
        worker
        for worker, rows in active_queues.items()
        if isinstance(rows, list)
        for row in rows
        if isinstance(row, dict) and _clean(row.get("name")) == queue_name
    )
    ready = bool(online_workers and queue_workers)
    return {
        "status": "healthy" if ready else "unhealthy",
        "ready": ready,
        "queue_name": queue_name,
        "checked_at": time.time(),
        "online_workers": online_workers,
        "queue_workers": queue_workers,
        "active_queues": active_queues,
    }


def wait_for_queue_ready(
    *,
    queue_name: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> Dict[str, Any]:
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    last_payload: Dict[str, Any] = {"status": "unhealthy", "ready": False, "queue_name": queue_name, "checked_at": time.time()}
    while True:
        last_payload = _inspect_ready(queue_name, timeout_seconds=max(0.5, poll_interval_seconds))
        if bool(last_payload.get("ready")):
            return last_payload
        if time.monotonic() >= deadline:
            return last_payload
        time.sleep(max(0.1, float(poll_interval_seconds)))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Wait for the LMCP Celery operations worker to become ready.")
    parser.add_argument("--queue", default="operations_queue")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    payload = wait_for_queue_ready(
        queue_name=str(args.queue),
        timeout_seconds=float(args.timeout_seconds),
        poll_interval_seconds=float(args.poll_interval_seconds),
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0 if bool(payload.get("ready")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
