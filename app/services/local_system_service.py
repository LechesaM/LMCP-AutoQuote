from __future__ import annotations

import json
import socket
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from app.core.runtime_paths import get_runtime_paths

RUNTIME_DIR = get_runtime_paths().runtime_root
LOCAL_SYSTEM_STATUS_FILE = RUNTIME_DIR / "local_system_status.json"

BACKEND_HOST = "127.0.0.1"
BACKEND_PORTS: Sequence[int] = (8000, 8001, 8002)
DEFAULT_FRONTEND_URL = "http://127.0.0.1:5173"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _port_from_url(url: str) -> Optional[int]:
    try:
        parsed = urlparse(str(url).strip())
        return int(parsed.port) if parsed.port else None
    except Exception:
        return None


def _read_json_url(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    payload = json.loads(raw or "{}")
    return payload if isinstance(payload, dict) else {"raw": payload}


def _probe_url(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(256).decode("utf-8", errors="replace")
            return {
                "available": True,
                "status": "online",
                "url": url,
                "http_status": int(getattr(response, "status", 200) or 200),
                "body_preview": body[:120],
                "error": "",
            }
    except Exception as exc:
        return {
            "available": False,
            "status": "offline",
            "url": url,
            "http_status": None,
            "body_preview": "",
            "error": str(exc),
        }


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, int(port))) != 0


def pick_backend_port(host: str = BACKEND_HOST, ports: Sequence[int] = BACKEND_PORTS) -> Optional[int]:
    for port in ports:
        if is_port_available(host, int(port)):
            return int(port)
    return None


def probe_backend_health(backend_url: str, timeout: float = 2.0) -> Dict[str, Any]:
    health_url = f"{str(backend_url).rstrip('/')}/health"
    try:
        payload = _read_json_url(health_url, timeout=timeout)
    except Exception as exc:
        return {
            "available": False,
            "status": "offline",
            "url": _clean(backend_url),
            "health_url": health_url,
            "error": str(exc),
            "payload": {},
        }

    health_status = _clean(payload.get("status") or "unknown")
    return {
        "available": True,
        "status": "healthy" if health_status == "healthy" else "warning",
        "url": _clean(backend_url),
        "health_url": health_url,
        "error": "",
        "payload": payload,
    }


def probe_frontend(frontend_url: str, timeout: float = 2.0) -> Dict[str, Any]:
    return _probe_url(frontend_url, timeout=timeout)


def build_local_system_status(
    *,
    backend_port: Optional[int],
    backend_url: str,
    frontend_url: str,
    backend_probe: Dict[str, Any],
    frontend_probe: Dict[str, Any],
    backend_pid: Optional[int] = None,
    frontend_pid: Optional[int] = None,
    backend_command: str = "",
    frontend_command: str = "",
) -> Dict[str, Any]:
    backend_status = _clean(backend_probe.get("status") or "offline")
    frontend_status = _clean(frontend_probe.get("status") or "offline")

    if backend_status == "healthy" and frontend_status == "online":
        overall_status = "ready"
    elif backend_probe.get("available") or frontend_probe.get("available"):
        overall_status = "degraded"
    else:
        overall_status = "blocked"

    return {
        "status": overall_status,
        "mode": "local_manual_production",
        "updated_at": _now_iso(),
        "backend": {
            "host": BACKEND_HOST,
            "port": backend_port,
            "url": _clean(backend_url),
            "pid": backend_pid,
            "command": backend_command,
            "status": backend_status,
            "available": bool(backend_probe.get("available", False)),
            "health_url": backend_probe.get("health_url"),
            "error": _clean(backend_probe.get("error")),
            "payload": backend_probe.get("payload") or {},
        },
        "frontend": {
            "url": _clean(frontend_url),
            "pid": frontend_pid,
            "command": frontend_command,
            "status": frontend_status,
            "available": bool(frontend_probe.get("available", False)),
            "error": _clean(frontend_probe.get("error")),
            "http_status": frontend_probe.get("http_status"),
            "body_preview": frontend_probe.get("body_preview", ""),
        },
    }


def write_local_system_status(status: Dict[str, Any], status_path: Path = LOCAL_SYSTEM_STATUS_FILE) -> Path:
    status_path = Path(status_path)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    return status_path


def load_local_system_status(status_path: Path = LOCAL_SYSTEM_STATUS_FILE) -> Dict[str, Any]:
    status_path = Path(status_path)
    if not status_path.exists():
        return {}
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def refresh_local_system_status(
    *,
    backend_url: Optional[str] = None,
    frontend_url: Optional[str] = None,
    backend_port: Optional[int] = None,
    backend_pid: Optional[int] = None,
    frontend_pid: Optional[int] = None,
    backend_command: str = "",
    frontend_command: str = "",
    status_path: Path = LOCAL_SYSTEM_STATUS_FILE,
    backend_probe_fn: Callable[[str], Dict[str, Any]] = probe_backend_health,
    frontend_probe_fn: Callable[[str], Dict[str, Any]] = probe_frontend,
) -> Dict[str, Any]:
    backend_port = int(backend_port) if backend_port is not None else None
    existing_status = load_local_system_status(status_path)
    if backend_url is None:
        existing_backend = existing_status.get("backend") if isinstance(existing_status.get("backend"), dict) else {}
        backend_url = _clean(existing_backend.get("url"))
        if backend_port is None and backend_url:
            backend_port = _port_from_url(backend_url)
        if not backend_url and backend_port is None:
            backend_port = pick_backend_port()
            backend_url = f"http://{BACKEND_HOST}:{backend_port}" if backend_port is not None else ""

    if frontend_url is None:
        existing_frontend = existing_status.get("frontend") if isinstance(existing_status.get("frontend"), dict) else {}
        frontend_url = _clean(existing_frontend.get("url")) or DEFAULT_FRONTEND_URL

    backend_probe = backend_probe_fn(backend_url) if backend_url else {
        "available": False,
        "status": "offline",
        "url": "",
        "health_url": "",
        "error": "Backend URL not available",
        "payload": {},
    }
    frontend_probe = frontend_probe_fn(frontend_url) if frontend_url else {
        "available": False,
        "status": "offline",
        "url": "",
        "http_status": None,
        "body_preview": "",
        "error": "Frontend URL not available",
    }

    status = build_local_system_status(
        backend_port=backend_port,
        backend_url=backend_url,
        frontend_url=frontend_url,
        backend_probe=backend_probe,
        frontend_probe=frontend_probe,
        backend_pid=backend_pid,
        frontend_pid=frontend_pid,
        backend_command=backend_command,
        frontend_command=frontend_command,
    )
    write_local_system_status(status, status_path=status_path)
    status["status_file"] = str(Path(status_path))
    return status
