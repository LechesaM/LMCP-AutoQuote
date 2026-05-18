from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.local_system_service import (
    LOCAL_SYSTEM_STATUS_FILE,
    refresh_local_system_status,
    pick_backend_port,
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _print_summary(status: Dict[str, Any]) -> None:
    backend = status.get("backend") if isinstance(status.get("backend"), dict) else {}
    frontend = status.get("frontend") if isinstance(status.get("frontend"), dict) else {}
    print(f"overall_status: {_clean(status.get('status'))}")
    print(f"backend_url: {_clean(backend.get('url'))}")
    print(f"backend_status: {_clean(backend.get('status'))}")
    print(f"backend_available: {str(bool(backend.get('available', False))).lower()}")
    print(f"frontend_url: {_clean(frontend.get('url'))}")
    print(f"frontend_status: {_clean(frontend.get('status'))}")
    print(f"frontend_available: {str(bool(frontend.get('available', False))).lower()}")
    print(f"status_file: {_clean(status.get('status_file') or LOCAL_SYSTEM_STATUS_FILE)}")
    if _clean(backend.get("error")):
        print(f"backend_error: {_clean(backend.get('error'))}")
    if _clean(frontend.get("error")):
        print(f"frontend_error: {_clean(frontend.get('error'))}")


def _wait_for_status(
    *,
    backend_url: Optional[str],
    frontend_url: Optional[str],
    status_path: Path,
    wait_seconds: int,
) -> Dict[str, Any]:
    deadline = time.monotonic() + max(0, int(wait_seconds))
    last_status: Dict[str, Any] = {}

    while True:
        last_status = refresh_local_system_status(
            backend_url=backend_url,
            frontend_url=frontend_url,
            status_path=status_path,
        )
        if _clean(last_status.get("status")) == "ready":
            return last_status
        if time.monotonic() >= deadline:
            return last_status
        time.sleep(1)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check local manual-production backend and frontend state.")
    parser.add_argument("--backend-url", default=None, help="Backend base URL, if already known.")
    parser.add_argument("--frontend-url", default=None, help="Frontend base URL, if already known.")
    parser.add_argument(
        "--status-path",
        default=str(LOCAL_SYSTEM_STATUS_FILE),
        help="Path to runtime/local_system_status.json.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=0,
        help="Optional wait time to poll until the system becomes ready.",
    )
    parser.add_argument(
        "--select-backend-port",
        action="store_true",
        help="Print the first available backend port from 8000/8001/8002 and exit.",
    )
    args = parser.parse_args(argv)

    if args.select_backend_port:
        port = pick_backend_port()
        if port is None:
            return 1
        print(port)
        return 0

    status = _wait_for_status(
        backend_url=args.backend_url,
        frontend_url=args.frontend_url,
        status_path=Path(args.status_path),
        wait_seconds=args.wait_seconds,
    )
    _print_summary(status)
    return 0 if _clean(status.get("status")) == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
