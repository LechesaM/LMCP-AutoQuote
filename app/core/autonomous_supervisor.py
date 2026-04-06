import os
import time
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Callable, Any, Optional

from app.core.stability_guard import guard

logger = logging.getLogger("lmcp.autonomous_supervisor")


class AutonomousSupervisor:
    """
    Crash-proof wrapper for the autonomous procurement loop.

    Purpose:
    - keep autonomous jobs running continuously
    - stop overlapping executions
    - survive temporary failures
    - slow down after repeated crashes
    - expose machine-readable status
    """

    def __init__(self) -> None:
        self.runtime_dir = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime"))
        self.supervisor_dir = self.runtime_dir / "supervisor"
        self.supervisor_dir.mkdir(parents=True, exist_ok=True)

        self.status_file = self.supervisor_dir / "autonomous_supervisor_status.json"
        self.history_file = self.supervisor_dir / "autonomous_supervisor_history.json"

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _write_json(self, path: Path, payload: dict) -> None:
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp.replace(path)

    def _append_history(self, event: dict) -> None:
        history = []
        if self.history_file.exists():
            try:
                history = json.loads(self.history_file.read_text(encoding="utf-8"))
                if not isinstance(history, list):
                    history = []
            except Exception:
                history = []

        history.append(event)
        history = history[-200:]  # keep latest 200 events only
        self._write_json(self.history_file, history)

    def write_status(
        self,
        state: str,
        message: str,
        *,
        cycle: int = 0,
        consecutive_failures: int = 0,
        last_success_at: Optional[str] = None,
        last_error: Optional[str] = None,
        sleep_seconds: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        payload = {
            "timestamp": self._utc_now(),
            "state": state,
            "message": message,
            "cycle": cycle,
            "consecutive_failures": consecutive_failures,
            "last_success_at": last_success_at,
            "last_error": last_error,
            "sleep_seconds": sleep_seconds,
        }
        if extra:
            payload["extra"] = extra

        self._write_json(self.status_file, payload)
        self._append_history(payload)
        return payload

    def read_status(self) -> dict:
        if not self.status_file.exists():
            return {
                "timestamp": self._utc_now(),
                "state": "not_started",
                "message": "Supervisor has not started yet.",
            }

        try:
            return json.loads(self.status_file.read_text(encoding="utf-8"))
        except Exception as e:
            return {
                "timestamp": self._utc_now(),
                "state": "error",
                "message": "Could not read supervisor status file.",
                "last_error": str(e),
            }

    def run_forever(
        self,
        job_callable: Callable[..., Any],
        *job_args,
        loop_name: str = "autonomous_supervised_loop",
        base_interval_seconds: int = 300,
        max_backoff_seconds: int = 3600,
        max_consecutive_failures_before_long_pause: int = 5,
        job_timeout_note: Optional[str] = None,
        **job_kwargs,
    ) -> None:
        """
        Runs the autonomous job forever with lock protection and recovery logic.

        Example:
            supervisor.run_forever(run_full_autonomous_pipeline, db_session_factory)
        """
        cycle = 0
        consecutive_failures = 0
        last_success_at = None

        self.write_status(
            "starting",
            "Autonomous supervisor is starting.",
            cycle=cycle,
            consecutive_failures=consecutive_failures,
        )

        logger.info("Autonomous supervisor started")

        while True:
            cycle += 1

            try:
                guard.heartbeat(
                    "autonomous_supervisor",
                    {
                        "cycle": cycle,
                        "state": "running",
                    },
                )

                self.write_status(
                    "running",
                    "Starting supervised autonomous cycle.",
                    cycle=cycle,
                    consecutive_failures=consecutive_failures,
                    last_success_at=last_success_at,
                    extra={
                        "loop_name": loop_name,
                        "job_timeout_note": job_timeout_note,
                    },
                )

                with guard.file_lock(loop_name):
                    result = guard.run_with_retries(
                        loop_name,
                        job_callable,
                        *job_args,
                        retries=3,
                        delay_seconds=5,
                        backoff=2,
                        **job_kwargs,
                    )

                consecutive_failures = 0
                last_success_at = self._utc_now()

                self.write_status(
                    "healthy",
                    "Autonomous cycle completed successfully.",
                    cycle=cycle,
                    consecutive_failures=consecutive_failures,
                    last_success_at=last_success_at,
                    extra={
                        "result_type": str(type(result).__name__),
                    },
                )

                logger.info(
                    "Autonomous cycle %s completed successfully. Sleeping %ss",
                    cycle,
                    base_interval_seconds,
                )
                time.sleep(base_interval_seconds)

            except Exception as e:
                consecutive_failures += 1
                error_text = str(e)

                logger.exception(
                    "Autonomous cycle %s failed. Consecutive failures: %s",
                    cycle,
                    consecutive_failures,
                )

                backoff_seconds = min(
                    base_interval_seconds * max(1, consecutive_failures),
                    max_backoff_seconds,
                )

                if consecutive_failures >= max_consecutive_failures_before_long_pause:
                    backoff_seconds = max(backoff_seconds, 1800)

                self.write_status(
                    "degraded",
                    "Autonomous cycle failed, supervisor will retry automatically.",
                    cycle=cycle,
                    consecutive_failures=consecutive_failures,
                    last_success_at=last_success_at,
                    last_error=error_text,
                    sleep_seconds=backoff_seconds,
                    extra={
                        "traceback": traceback.format_exc(),
                    },
                )

                guard.heartbeat(
                    "autonomous_supervisor",
                    {
                        "cycle": cycle,
                        "state": "degraded",
                        "consecutive_failures": consecutive_failures,
                    },
                )

                time.sleep(backoff_seconds)


supervisor = AutonomousSupervisor()
