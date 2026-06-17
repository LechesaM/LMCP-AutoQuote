#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.runtime_paths import resolve_project_root


DEFAULT_HEALTH_TIMEOUT = 60.0
DEFAULT_HEALTH_POLL_INTERVAL = 1.0


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}


def _project_root() -> Path:
    return resolve_project_root()


def _probe_health(health_url: str, timeout: float = 3.0) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "curl",
                "-fsS",
                "--max-time",
                str(timeout),
                health_url,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return {"status": "unhealthy", "health_url": health_url, "error": str(exc)}

    if result.returncode != 0:
        error_text = (result.stderr or result.stdout or "").strip()
        return {
            "status": "unhealthy",
            "health_url": health_url,
            "error": error_text or f"curl exited with status {result.returncode}",
        }

    body = (result.stdout or "").strip()
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {"raw": body}
    if isinstance(payload, dict):
        payload.setdefault("status", "healthy")
        payload.setdefault("health_url", health_url)
        return payload
    return {"status": "healthy", "health_url": health_url, "payload": payload}


def _tail_file(path: Path, lines: int = 80) -> str:
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    return "\n".join(content[-lines:])


def _start_api(host: str, port: str, log_file: Path) -> subprocess.Popen[Any]:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_file.open("ab", buffering=0)
    env = os.environ.copy()
    project_root = str(_project_root())
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{project_root}{os.pathsep}{pythonpath}" if pythonpath else project_root
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=project_root,
        env=env,
        stdout=log_handle,
        stderr=log_handle,
        start_new_session=True,
    )


def _wait_for_health(health_url: str, timeout: float, poll_interval: float) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_payload: Dict[str, Any] = {"status": "unhealthy", "health_url": health_url, "error": "health check not attempted"}
    while time.monotonic() < deadline:
        payload = _probe_health(health_url, timeout=min(3.0, max(0.5, poll_interval)))
        last_payload = payload
        if str(payload.get("status", "")).lower() == "healthy":
            return payload
        time.sleep(max(0.1, poll_interval))
    return last_payload


def ensure_api_session(
    *,
    health_url: str,
    host: str,
    port: str,
    bootstrap: bool,
    health_timeout: float,
    poll_interval: float,
    log_file: Path,
) -> Dict[str, Any]:
    health = _probe_health(health_url)
    if str(health.get("status", "")).lower() == "healthy":
        return {
            "status": "healthy",
            "started": False,
            "pid": None,
            "bootstrapped": False,
            "health": health,
            "health_url": health_url,
            "log_file": str(log_file),
        }

    if not bootstrap:
        raise RuntimeError(
            f"API at {health_url} is unhealthy and bootstrap is disabled; set LMCP_API_BOOTSTRAP=1 to allow startup."
        )

    process = _start_api(host, port, log_file)
    health = _wait_for_health(health_url, timeout=health_timeout, poll_interval=poll_interval)
    if str(health.get("status", "")).lower() == "healthy":
        return {
            "status": "healthy",
            "started": True,
            "pid": process.pid,
            "bootstrapped": True,
            "health": health,
            "health_url": health_url,
            "log_file": str(log_file),
        }

    process.terminate()
    try:
        process.wait(timeout=5)
    except Exception:
        process.kill()
        process.wait(timeout=5)

    message = _tail_file(log_file)
    raise RuntimeError(
        f"API failed to become healthy at {health_url}; last health response: {json.dumps(health, sort_keys=True)}"
        + (f"\nAPI log tail:\n{message}" if message else "")
    )


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure the local LMCP API is healthy, bootstrapping it if needed.")
    parser.add_argument("--api-base", default=os.getenv("API_BASE", "http://127.0.0.1:8011"))
    parser.add_argument("--host", default=os.getenv("API_HOST", "127.0.0.1"))
    parser.add_argument("--port", default=os.getenv("API_PORT", "8011"))
    parser.add_argument(
        "--bootstrap",
        dest="bootstrap",
        action="store_true",
        help="Start the API if it is not already healthy.",
    )
    parser.add_argument(
        "--no-bootstrap",
        dest="bootstrap",
        action="store_false",
        help="Require the API to already be healthy.",
    )
    parser.set_defaults(bootstrap=_env_flag("LMCP_API_BOOTSTRAP", True))
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=float(os.getenv("LMCP_API_HEALTH_TIMEOUT", DEFAULT_HEALTH_TIMEOUT)),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("LMCP_API_POLL_INTERVAL", DEFAULT_HEALTH_POLL_INTERVAL)),
    )
    parser.add_argument(
        "--log-file",
        default=os.getenv("API_LOG", str(_project_root() / "runtime" / "logs" / "run_local_rfq_happy_path_api.log")),
    )
    parser.add_argument("--pid-file", default=os.getenv("API_PID_FILE", ""))
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    log_file = Path(args.log_file).expanduser().resolve()
    health_url = f"{args.api_base.rstrip('/')}/health"

    try:
        payload = ensure_api_session(
            health_url=health_url,
            host=str(args.host),
            port=str(args.port),
            bootstrap=bool(args.bootstrap),
            health_timeout=float(args.health_timeout),
            poll_interval=float(args.poll_interval),
            log_file=log_file,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "unhealthy",
                    "health_url": health_url,
                    "error": str(exc),
                    "bootstrap": bool(args.bootstrap),
                    "log_file": str(log_file),
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1

    pid_file = str(args.pid_file).strip()
    if pid_file:
        pid_path = Path(pid_file).expanduser().resolve()
        if payload.get("started") and payload.get("pid"):
            pid_path.parent.mkdir(parents=True, exist_ok=True)
            pid_path.write_text(str(payload["pid"]), encoding="utf-8")
        elif pid_path.exists():
            pid_path.unlink()

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
