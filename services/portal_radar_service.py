import logging
import threading
import time
from typing import Any, Dict

from app.scripts.portal_radar_diagnostic import load_portals, run_parallel_diagnostic

logger = logging.getLogger("autoquote.portal_radar")

_PORTAL_RADAR_CACHE: Dict[str, Any] = {
    "generated_at": None,
    "total_portals": 0,
    "scan_duration_seconds": 0,
    "summary": {
        "healthy": 0,
        "slow": 0,
        "broken": 0,
        "blocked": 0,
    },
    "slowest_20": [],
    "results": [],
    "status": "not_started",
    "message": "Portal radar has not started yet.",
}

_CACHE_LOCK = threading.Lock()
_RADAR_THREAD_STARTED = False


def _safe_store(report: Dict[str, Any], status: str = "ok", message: str = "") -> None:
    with _CACHE_LOCK:
        _PORTAL_RADAR_CACHE.clear()
        _PORTAL_RADAR_CACHE.update(report)
        _PORTAL_RADAR_CACHE["status"] = status
        _PORTAL_RADAR_CACHE["message"] = message or "Portal radar cache updated successfully."


def _safe_error(message: str) -> None:
    with _CACHE_LOCK:
        _PORTAL_RADAR_CACHE["status"] = "error"
        _PORTAL_RADAR_CACHE["message"] = message


def refresh_portal_radar_once() -> Dict[str, Any]:
    try:
        logger.info("Starting portal radar refresh...")
        portals = load_portals()
        report = run_parallel_diagnostic(portals)
        _safe_store(report, status="ok", message="Portal radar refresh completed.")
        logger.info("Portal radar refresh completed: %s portals scanned.", report.get("total_portals", 0))
        return report
    except Exception as exc:
        logger.exception("Portal radar refresh failed: %s", exc)
        _safe_error(f"Portal radar refresh failed: {exc}")
        return get_portal_radar_cache()


def get_portal_radar_cache() -> Dict[str, Any]:
    with _CACHE_LOCK:
        return dict(_PORTAL_RADAR_CACHE)


def get_portal_radar_summary() -> Dict[str, Any]:
    data = get_portal_radar_cache()
    summary = data.get("summary", {})
    total = data.get("total_portals", 0)

    return {
        "status": data.get("status", "unknown"),
        "message": data.get("message", ""),
        "generated_at": data.get("generated_at"),
        "scan_duration_seconds": data.get("scan_duration_seconds", 0),
        "total_portals": total,
        "healthy": summary.get("healthy", 0),
        "slow": summary.get("slow", 0),
        "broken": summary.get("broken", 0),
        "blocked": summary.get("blocked", 0),
        "health_score_percent": round(
            ((summary.get("healthy", 0) / total) * 100), 2
        ) if total else 0.0,
    }


def start_portal_radar_background_loop(interval_seconds: int = 900) -> None:
    global _RADAR_THREAD_STARTED

    if _RADAR_THREAD_STARTED:
        logger.info("Portal radar background loop already running.")
        return

    def _runner() -> None:
        logger.info("Portal radar background loop started. Interval=%s sec", interval_seconds)
        while True:
            try:
                refresh_portal_radar_once()
            except Exception as exc:
                logger.exception("Unexpected portal radar loop failure: %s", exc)
                _safe_error(f"Unexpected portal radar loop failure: {exc}")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_runner, name="portal-radar-loop", daemon=True)
    thread.start()
    _RADAR_THREAD_STARTED = True
