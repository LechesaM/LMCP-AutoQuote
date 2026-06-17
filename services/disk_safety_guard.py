import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class DiskSafetyStatus:
    enabled: bool = True
    threshold_gb: float = 10.0
    cooldown_minutes: int = 30
    last_check_at: Optional[str] = None
    last_triggered_at: Optional[str] = None
    last_cleanup_at: Optional[str] = None
    last_restart_at: Optional[str] = None
    last_error: Optional[str] = None
    current_free_gb: float = 0.0
    current_used_percent: float = 0.0
    harvester_pause_file: str = ""
    lock_file: str = ""
    is_paused: bool = False
    guard_running: bool = False
    last_action: str = "idle"


class DiskSafetyGuard:
    """
    Protects the system from low-disk crashes.

    When free disk space drops below threshold:
      1. pause harvester
      2. clean Docker
      3. optionally run local cleanup script
      4. restart Docker Compose services safely
      5. keep cooldown to prevent restart loops
    """

    def __init__(
        self,
        project_root: str = "/Users/Shared/LMCP-AutoQuote-Server",
        threshold_gb: float = 10.0,
        cooldown_minutes: int = 30,
        docker_compose_file: str = "docker-compose.yml",
        cleanup_script: str = "docker_cleanup.sh",
        enabled: bool = True,
    ) -> None:
        self.project_root = project_root
        self.threshold_gb = threshold_gb
        self.cooldown_minutes = cooldown_minutes
        self.docker_compose_file = docker_compose_file
        self.cleanup_script = cleanup_script
        self.enabled = enabled

        runtime_root = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
        runtime_dir = runtime_root / "disk_safety_guard"
        self.runtime_dir = str(runtime_dir)
        self.pause_file = str(runtime_dir / "harvester.paused")
        self.lock_file = str(runtime_dir / "disk_guard.lock")

        os.makedirs(self.runtime_dir, exist_ok=True)

        self.status = DiskSafetyStatus(
            enabled=enabled,
            threshold_gb=threshold_gb,
            cooldown_minutes=cooldown_minutes,
            harvester_pause_file=self.pause_file,
            lock_file=self.lock_file,
        )

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def get_disk_metrics(self) -> Dict[str, float]:
        usage = shutil.disk_usage(self.project_root)
        total_gb = usage.total / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        used_percent = (usage.used / usage.total) * 100 if usage.total else 0.0
        return {
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "used_percent": round(used_percent, 2),
        }

    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def _write_pause_file(self, reason: str) -> None:
        with open(self.pause_file, "w", encoding="utf-8") as f:
            f.write(f"paused_at={self._now()}\n")
            f.write(f"reason={reason}\n")

    def _remove_pause_file(self) -> None:
        if os.path.exists(self.pause_file):
            os.remove(self.pause_file)

    def pause_harvester(self, reason: str = "low_disk_space") -> None:
        self._write_pause_file(reason)
        self.status.is_paused = True
        self.status.last_action = f"harvester_paused:{reason}"
        logger.warning("Harvester paused: %s", reason)

    def resume_harvester(self) -> None:
        self._remove_pause_file()
        self.status.is_paused = False
        self.status.last_action = "harvester_resumed"
        logger.info("Harvester resumed")

    def is_harvester_paused(self) -> bool:
        return os.path.exists(self.pause_file)

    def _run_command(self, cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
        logger.info("Running command: %s", " ".join(cmd))
        return subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def docker_cleanup(self) -> Dict[str, Any]:
        result_summary: Dict[str, Any] = {"ok": True, "steps": []}

        commands = [
            ["docker", "container", "prune", "-f"],
            ["docker", "image", "prune", "-a", "-f"],
            ["docker", "volume", "prune", "-f"],
            ["docker", "network", "prune", "-f"],
            ["docker", "builder", "prune", "-a", "-f"],
        ]

        for cmd in commands:
            try:
                result = self._run_command(cmd, timeout=300)
                step = {
                    "command": " ".join(cmd),
                    "returncode": result.returncode,
                    "stdout": result.stdout[-2000:],
                    "stderr": result.stderr[-2000:],
                }
                result_summary["steps"].append(step)
                if result.returncode != 0:
                    result_summary["ok"] = False
            except Exception as exc:
                result_summary["ok"] = False
                result_summary["steps"].append(
                    {
                        "command": " ".join(cmd),
                        "returncode": -1,
                        "stdout": "",
                        "stderr": str(exc),
                    }
                )

        cleanup_script_path = os.path.join(self.project_root, self.cleanup_script)
        if os.path.exists(cleanup_script_path):
            try:
                result = self._run_command(["bash", cleanup_script_path], timeout=600)
                result_summary["steps"].append(
                    {
                        "command": f"bash {cleanup_script_path}",
                        "returncode": result.returncode,
                        "stdout": result.stdout[-2000:],
                        "stderr": result.stderr[-2000:],
                    }
                )
                if result.returncode != 0:
                    result_summary["ok"] = False
            except Exception as exc:
                result_summary["ok"] = False
                result_summary["steps"].append(
                    {
                        "command": f"bash {cleanup_script_path}",
                        "returncode": -1,
                        "stdout": "",
                        "stderr": str(exc),
                    }
                )

        self.status.last_cleanup_at = self._now()
        self.status.last_action = "docker_cleanup_run"
        return result_summary

    def restart_stack(self) -> Dict[str, Any]:
        compose_path = os.path.join(self.project_root, self.docker_compose_file)
        if not os.path.exists(compose_path):
            return {
                "ok": False,
                "message": f"Compose file not found: {compose_path}",
            }

        result_bundle: Dict[str, Any] = {"ok": True, "steps": []}

        commands = [
            ["docker", "compose", "-f", compose_path, "down"],
            ["docker", "compose", "-f", compose_path, "up", "-d"],
        ]

        for cmd in commands:
            try:
                result = self._run_command(cmd, timeout=600)
                step = {
                    "command": " ".join(cmd),
                    "returncode": result.returncode,
                    "stdout": result.stdout[-3000:],
                    "stderr": result.stderr[-3000:],
                }
                result_bundle["steps"].append(step)
                if result.returncode != 0:
                    result_bundle["ok"] = False
            except Exception as exc:
                result_bundle["ok"] = False
                result_bundle["steps"].append(
                    {
                        "command": " ".join(cmd),
                        "returncode": -1,
                        "stdout": "",
                        "stderr": str(exc),
                    }
                )

        self.status.last_restart_at = self._now()
        self.status.last_action = "stack_restarted"
        return result_bundle

    def in_cooldown(self) -> bool:
        if not self.status.last_triggered_at:
            return False

        try:
            last = datetime.fromisoformat(self.status.last_triggered_at.replace("Z", ""))
            delta_seconds = (datetime.utcnow() - last).total_seconds()
            return delta_seconds < self.cooldown_minutes * 60
        except Exception:
            return False

    def check_once(self) -> Dict[str, Any]:
        metrics = self.get_disk_metrics()
        self.status.last_check_at = self._now()
        self.status.current_free_gb = metrics["free_gb"]
        self.status.current_used_percent = metrics["used_percent"]
        self.status.is_paused = self.is_harvester_paused()

        response: Dict[str, Any] = {
            "ok": True,
            "triggered": False,
            "metrics": metrics,
            "status": asdict(self.status),
        }

        if not self.enabled:
            self.status.last_action = "guard_disabled"
            response["message"] = "DiskSafetyGuard disabled"
            response["status"] = asdict(self.status)
            return response

        if metrics["free_gb"] >= self.threshold_gb:
            self.status.last_action = "healthy"
            response["message"] = "Disk space healthy"
            response["status"] = asdict(self.status)
            return response

        if self.in_cooldown():
            self.status.last_action = "low_disk_but_in_cooldown"
            response["triggered"] = False
            response["message"] = "Low disk detected, but cooldown active"
            response["status"] = asdict(self.status)
            return response

        self.status.last_triggered_at = self._now()
        response["triggered"] = True
        response["message"] = "Low disk detected; safety workflow triggered"

        try:
            self.pause_harvester("low_disk_space")
            cleanup_result = self.docker_cleanup()
            restart_result = self.restart_stack()

            post_metrics = self.get_disk_metrics()
            self.status.current_free_gb = post_metrics["free_gb"]
            self.status.current_used_percent = post_metrics["used_percent"]

            if post_metrics["free_gb"] >= self.threshold_gb:
                self.resume_harvester()

            response["actions"] = {
                "cleanup": cleanup_result,
                "restart": restart_result,
                "post_metrics": post_metrics,
            }
            response["status"] = asdict(self.status)

        except Exception as exc:
            self.status.last_error = str(exc)
            self.status.last_action = "error"
            response["ok"] = False
            response["error"] = str(exc)
            response["status"] = asdict(self.status)

        return response

    def start_background_monitor(self, interval_seconds: int = 300) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("DiskSafetyGuard background monitor already running")
            return

        self._stop_event.clear()

        def _loop() -> None:
            self.status.guard_running = True
            logger.info("DiskSafetyGuard started with %ss interval", interval_seconds)
            while not self._stop_event.is_set():
                try:
                    self.check_once()
                except Exception as exc:
                    self.status.last_error = str(exc)
                    logger.exception("DiskSafetyGuard background error: %s", exc)
                time.sleep(interval_seconds)
            self.status.guard_running = False
            logger.info("DiskSafetyGuard stopped")

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_background_monitor(self) -> None:
        self._stop_event.set()

    def snapshot(self) -> Dict[str, Any]:
        metrics = self.get_disk_metrics()
        self.status.current_free_gb = metrics["free_gb"]
        self.status.current_used_percent = metrics["used_percent"]
        self.status.is_paused = self.is_harvester_paused()
        return {
            "metrics": metrics,
            "status": asdict(self.status),
        }


disk_guard = DiskSafetyGuard(
    project_root=os.getenv("LMCP_PROJECT_ROOT", "/Users/Shared/LMCP-AutoQuote-Server"),
    threshold_gb=float(os.getenv("DISK_GUARD_THRESHOLD_GB", "10")),
    cooldown_minutes=int(os.getenv("DISK_GUARD_COOLDOWN_MINUTES", "30")),
    docker_compose_file=os.getenv("DISK_GUARD_COMPOSE_FILE", "docker-compose.yml"),
    cleanup_script=os.getenv("DISK_GUARD_CLEANUP_SCRIPT", "docker_cleanup.sh"),
    enabled=os.getenv("DISK_GUARD_ENABLED", "true").lower() == "true",
)
