from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class WatchdogState:
    last_checked_at: Optional[str] = None
    last_health_status: str = "unknown"
    last_restart_at: Optional[str] = None
    restart_count: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_dir() -> Path:
    root = Path(os.environ.get("LMCP_WATCHDOG_DIR") or (PROJECT_ROOT / "runtime" / "watchdog"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _state_path() -> Path:
    return _state_dir() / "backend_watchdog_state.json"


def _read_state() -> WatchdogState:
    path = _state_path()
    if not path.exists():
        return WatchdogState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WatchdogState(
            last_checked_at=data.get("last_checked_at"),
            last_health_status=str(data.get("last_health_status") or "unknown"),
            last_restart_at=data.get("last_restart_at"),
            restart_count=int(data.get("restart_count") or 0),
        )
    except Exception:
        return WatchdogState()


def _write_state(state: WatchdogState) -> None:
    _state_path().write_text(
        json.dumps(
            {
                "last_checked_at": state.last_checked_at,
                "last_health_status": state.last_health_status,
                "last_restart_at": state.last_restart_at,
                "restart_count": state.restart_count,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def check_health(backend_url: str, timeout_seconds: int = 5) -> Dict[str, Any]:
    url = f"{backend_url.rstrip('/')}/health"
    try:
        result = subprocess.run(
            ["curl", "-sS", "--max-time", str(max(1, int(timeout_seconds))), "-i", url],
            capture_output=True,
            text=True,
            check=False,
        )
        body = result.stdout or result.stderr or ""
        status = 0
        for line in body.splitlines():
            if line.startswith("HTTP/"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    status = int(parts[1])
                break
        return {
            "ok": 200 <= status < 300,
            "status": status,
            "body": body[:500],
            "checked_at": _now_iso(),
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {"ok": False, "status": 0, "body": str(exc), "checked_at": _now_iso()}


def should_restart(state: WatchdogState, cooldown_seconds: int) -> bool:
    if not state.last_restart_at:
        return True
    try:
        last_restart = datetime.fromisoformat(state.last_restart_at)
        age = (datetime.now(timezone.utc) - last_restart).total_seconds()
        return age >= max(0, cooldown_seconds)
    except Exception:
        return True


def restart_backend(start_command: str) -> subprocess.Popen[Any]:
    command = shlex.split(start_command) if isinstance(start_command, str) else list(start_command)
    log_path = _state_dir() / "backend_watchdog_restart.log"
    log_handle = open(log_path, "a", encoding="utf-8")
    return subprocess.Popen(
        command,
        shell=False,
        start_new_session=True,
        stdout=log_handle,
        stderr=log_handle,
        env=os.environ.copy(),
        cwd=str(Path(os.environ.get("LMCP_PROJECT_ROOT") or PROJECT_ROOT).resolve()),
    )


def wait_for_healthy_backend(
    backend_url: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: int = 1,
) -> Dict[str, Any]:
    deadline = time.time() + max(1, int(timeout_seconds))
    last_health: Dict[str, Any] = {"ok": False, "status": 0, "body": "startup wait not started", "checked_at": _now_iso()}
    while time.time() <= deadline:
        last_health = check_health(backend_url, timeout_seconds=max(1, int(poll_interval_seconds)))
        if last_health.get("ok"):
            return last_health
        time.sleep(max(1, int(poll_interval_seconds)))
    return last_health


def ensure_backend_running(
    backend_url: str,
    start_command: str,
    *,
    timeout_seconds: int = 5,
    cooldown_seconds: int = 120,
) -> Dict[str, Any]:
    state = _read_state()
    health = check_health(backend_url, timeout_seconds=timeout_seconds)
    state.last_checked_at = health["checked_at"]
    state.last_health_status = "healthy" if health["ok"] else "unhealthy"

    result: Dict[str, Any] = {
        "checked_at": state.last_checked_at,
        "health": health,
        "restarted": False,
        "restart_count": state.restart_count,
        "cooldown_seconds": cooldown_seconds,
    }

    if health["ok"]:
        _write_state(state)
        return result

    if not should_restart(state, cooldown_seconds):
        _write_state(state)
        result["cooldown_active"] = True
        return result

    restart_backend(start_command)
    state.last_restart_at = _now_iso()
    state.restart_count += 1
    state.last_health_status = "restarting"
    startup_timeout_seconds = int(os.environ.get("LMCP_WATCHDOG_STARTUP_TIMEOUT_SECONDS", "15"))
    recovered_health = wait_for_healthy_backend(backend_url, timeout_seconds=startup_timeout_seconds)
    if recovered_health.get("ok"):
        state.last_health_status = "healthy"
        state.last_checked_at = recovered_health.get("checked_at")
    _write_state(state)
    result.update(
        {
            "restarted": True,
            "restart_count": state.restart_count,
            "last_restart_at": state.last_restart_at,
            "startup_health": recovered_health,
        }
    )
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LMCP backend watchdog")
    parser.add_argument("--backend-url", default=os.environ.get("LMCP_BACKEND_URL", "http://127.0.0.1:8011"))
    parser.add_argument(
        "--start-command",
        default=os.environ.get(
            "LMCP_BACKEND_START_COMMAND",
            "python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8011",
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("LMCP_WATCHDOG_TIMEOUT_SECONDS", "5")))
    parser.add_argument("--cooldown-seconds", type=int, default=int(os.environ.get("LMCP_WATCHDOG_COOLDOWN_SECONDS", "120")))
    parser.add_argument("--loop", action="store_true", help="Keep checking and restarting if needed.")
    parser.add_argument("--interval-seconds", type=int, default=int(os.environ.get("LMCP_WATCHDOG_INTERVAL_SECONDS", "30")))
    args = parser.parse_args(argv)

    if args.loop:
        while True:
            print(json.dumps(ensure_backend_running(args.backend_url, args.start_command, timeout_seconds=args.timeout_seconds, cooldown_seconds=args.cooldown_seconds), indent=2))
            time.sleep(max(1, args.interval_seconds))
    else:
        print(json.dumps(ensure_backend_running(args.backend_url, args.start_command, timeout_seconds=args.timeout_seconds, cooldown_seconds=args.cooldown_seconds), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
