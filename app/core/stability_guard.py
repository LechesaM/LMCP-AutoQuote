# app/core/stability_guard.py

import os
import json
import time
import errno
import socket
import logging
import traceback
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Optional, Any

logger = logging.getLogger("lmcp.stability")


class StabilityGuard:
    """
    Central system stability layer for LMCP AutoQuote.

    What it does:
    - validates critical environment variables
    - waits for database / redis readiness
    - writes heartbeat files
    - creates lock files to stop overlapping runs
    - wraps unstable jobs with retries
    - provides startup diagnostics
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        resolved_base_dir = base_dir or os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")
        self.base_dir = Path(resolved_base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.lock_dir = self.base_dir / "locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        self.health_dir = self.base_dir / "health"
        self.health_dir.mkdir(parents=True, exist_ok=True)

        self.log_dir = self.base_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # BASIC INFO
    # ------------------------------------------------------------------

    def utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def write_json(self, path: Path, payload: dict) -> None:
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)

    # ------------------------------------------------------------------
    # ENV VALIDATION
    # ------------------------------------------------------------------

    def validate_environment(self) -> dict:
        """
        Validate required environment settings.
        Does not fail on optional items, but reports them.
        """
        required = [
            "DATABASE_URL",
        ]

        recommended = [
            "REDIS_URL",
            "ENVIRONMENT",
            "LOG_LEVEL",
        ]

        missing_required = [k for k in required if not os.getenv(k)]
        missing_recommended = [k for k in recommended if not os.getenv(k)]

        payload = {
            "timestamp": self.utc_now(),
            "required_ok": len(missing_required) == 0,
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "environment": {
                "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
                "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            },
        }

        self.write_json(self.health_dir / "env_check.json", payload)

        if missing_required:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing_required)}"
            )

        return payload

    # ------------------------------------------------------------------
    # SOCKET READINESS
    # ------------------------------------------------------------------

    def wait_for_tcp_service(
        self,
        host: str,
        port: int,
        name: str,
        timeout_seconds: int = 60,
        retry_interval: float = 2.0,
    ) -> dict:
        """
        Wait until a TCP service is reachable.
        Useful for postgres, redis, etc.
        """
        start = time.time()
        last_error = None

        while time.time() - start < timeout_seconds:
            try:
                with socket.create_connection((host, port), timeout=3):
                    payload = {
                        "service": name,
                        "host": host,
                        "port": port,
                        "ready": True,
                        "checked_at": self.utc_now(),
                    }
                    self.write_json(self.health_dir / f"{name}_ready.json", payload)
                    logger.info("%s is ready on %s:%s", name, host, port)
                    return payload
            except OSError as e:
                last_error = str(e)
                logger.warning("Waiting for %s on %s:%s ...", name, host, port)
                time.sleep(retry_interval)

        raise RuntimeError(
            f"{name} did not become ready on {host}:{port} within {timeout_seconds}s. "
            f"Last error: {last_error}"
        )

    def wait_for_default_dependencies(self) -> dict:
        """
        Auto-detects typical Docker service names and ports.
        Safe defaults for your stack.
        """
        results = {"timestamp": self.utc_now(), "services": []}

        postgres_host = os.getenv("POSTGRES_HOST", "db")
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))

        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        try:
            results["services"].append(
                self.wait_for_tcp_service(postgres_host, postgres_port, "postgres")
            )
        except Exception as e:
            logger.exception("Postgres readiness failed")
            raise RuntimeError(f"Postgres readiness failed: {e}") from e

        try:
            results["services"].append(
                self.wait_for_tcp_service(redis_host, redis_port, "redis")
            )
        except Exception as e:
            logger.exception("Redis readiness failed")
            raise RuntimeError(f"Redis readiness failed: {e}") from e

        self.write_json(self.health_dir / "dependency_check.json", results)
        return results

    # ------------------------------------------------------------------
    # HEARTBEAT
    # ------------------------------------------------------------------

    def heartbeat(self, component: str, extra: Optional[dict] = None) -> dict:
        payload = {
            "component": component,
            "timestamp": self.utc_now(),
            "pid": os.getpid(),
            "status": "alive",
        }
        if extra:
            payload.update(extra)

        self.write_json(self.health_dir / f"{component}_heartbeat.json", payload)
        return payload

    # ------------------------------------------------------------------
    # LOCKING
    # ------------------------------------------------------------------

    @contextmanager
    def file_lock(self, name: str):
        """
        Prevent overlapping jobs.
        Example:
            with guard.file_lock("autonomous_run_once"):
                do_work()
        """
        lock_path = self.lock_dir / f"{name}.lock"

        fd = None
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            os.close(fd)
            fd = None

            logger.info("Acquired lock: %s", lock_path.name)
            yield

        except OSError as e:
            if e.errno == errno.EEXIST:
                raise RuntimeError(
                    f"Another process is already running for lock '{name}'. "
                    f"Lock file exists: {lock_path}"
                ) from e
            raise

        finally:
            try:
                if fd is not None:
                    os.close(fd)
            except Exception:
                pass

            if lock_path.exists():
                try:
                    lock_path.unlink()
                    logger.info("Released lock: %s", lock_path.name)
                except Exception:
                    logger.warning("Could not remove lock file: %s", lock_path)

    # ------------------------------------------------------------------
    # RETRY WRAPPER
    # ------------------------------------------------------------------

    def run_with_retries(
        self,
        job_name: str,
        func: Callable[..., Any],
        *args,
        retries: int = 3,
        delay_seconds: float = 2.0,
        backoff: float = 2.0,
        **kwargs,
    ) -> Any:
        """
        Runs a function with controlled retries and logs failures safely.
        """
        attempt = 1
        current_delay = delay_seconds
        last_exception = None

        while attempt <= retries:
            try:
                logger.info("Running job '%s' attempt %s/%s", job_name, attempt, retries)
                result = func(*args, **kwargs)

                self.write_json(
                    self.health_dir / f"{job_name}_last_success.json",
                    {
                        "job_name": job_name,
                        "attempt": attempt,
                        "timestamp": self.utc_now(),
                        "status": "success",
                    },
                )
                return result

            except Exception as e:
                last_exception = e
                logger.exception("Job '%s' failed on attempt %s", job_name, attempt)

                self.write_json(
                    self.health_dir / f"{job_name}_last_error.json",
                    {
                        "job_name": job_name,
                        "attempt": attempt,
                        "timestamp": self.utc_now(),
                        "status": "error",
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )

                if attempt == retries:
                    break

                time.sleep(current_delay)
                current_delay *= backoff
                attempt += 1

        raise RuntimeError(
            f"Job '{job_name}' failed after {retries} attempts: {last_exception}"
        ) from last_exception

    # ------------------------------------------------------------------
    # STARTUP
    # ------------------------------------------------------------------

    def full_startup_check(self) -> dict:
        """
        Run this once during FastAPI startup.
        """
        logger.info("Starting StabilityGuard full startup check")

        env_status = self.validate_environment()
        deps_status = self.wait_for_default_dependencies()
        heartbeat = self.heartbeat("api_startup", {"phase": "startup_complete"})

        summary = {
            "timestamp": self.utc_now(),
            "status": "ok",
            "env": env_status,
            "dependencies": deps_status,
            "heartbeat": heartbeat,
        }

        self.write_json(self.health_dir / "startup_summary.json", summary)
        logger.info("StabilityGuard startup check completed successfully")
        return summary

    # ------------------------------------------------------------------
    # READ STATUS
    # ------------------------------------------------------------------

    def read_status(self) -> dict:
        """
        Safe status summary for API endpoint.
        """
        status = {
            "timestamp": self.utc_now(),
            "runtime_dir": str(self.base_dir),
            "health_files": [],
            "lock_files": [],
        }

        if self.health_dir.exists():
            for p in sorted(self.health_dir.glob("*.json")):
                status["health_files"].append(p.name)

        if self.lock_dir.exists():
            for p in sorted(self.lock_dir.glob("*.lock")):
                status["lock_files"].append(p.name)

        return status


guard = StabilityGuard()
