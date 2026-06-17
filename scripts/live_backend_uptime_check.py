#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRL = "/usr/bin/curl"


def _run(cmd: List[str], *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)


def _start_backend(host: str, port: str) -> subprocess.Popen[str]:
    log_file = PROJECT_ROOT / "runtime" / "logs" / "live_backend_uptime_check_api.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_file.open("ab", buffering=0)
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{pythonpath}" if pythonpath else str(PROJECT_ROOT)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            port,
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=log_handle,
        stderr=log_handle,
        start_new_session=True,
    )


def _curl_json(url: str, *, token: str | None = None, timeout: int = 10) -> Dict[str, Any]:
    cmd = [CURRL, "-sS", "--max-time", str(timeout)]
    if token:
        cmd.extend(["-H", f"Authorization: Bearer {token}"])
    cmd.append(url)
    result = _run(cmd, timeout=max(timeout + 5, 15))
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"request failed for {url}")
    body = result.stdout.strip()
    if not body:
        return {}
    return json.loads(body)


def _curl_text(url: str, *, token: str | None = None, timeout: int = 10) -> str:
    cmd = [CURRL, "-sS", "--max-time", str(timeout)]
    if token:
        cmd.extend(["-H", f"Authorization: Bearer {token}"])
    cmd.append(url)
    result = _run(cmd, timeout=max(timeout + 5, 15))
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"request failed for {url}")
    return result.stdout


def _login(api_base: str) -> str:
    result = _run(
        [
            CURRL,
            "-sS",
            "--max-time",
            "10",
            "-X",
            "POST",
            f"{api_base.rstrip('/')}/auth/login",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps({"email": "supervisor@lmcp.local", "password": "supervisor"}),
        ],
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "login failed")
    payload = json.loads(result.stdout.strip() or "{}")
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError(f"login did not return a token: {json.dumps(payload, sort_keys=True)}")
    return token


def _assert_paper(token: str, api_base: str) -> Dict[str, Any]:
    payload = _curl_json(f"{api_base.rstrip('/')}/operations/rfqs/PAPER", token=token, timeout=10)
    execution = payload.get("submission_execution") or {}
    package = payload.get("submission_package") or {}
    bundle = payload.get("review_ready_bundle") or {}
    blockers = execution.get("blockers") or []
    checks = {
        "review_ready": bool(bundle.get("review_ready")),
        "approval_ready": bool(package.get("approval_ready")),
        "submission_ready": bool(package.get("submission_ready")),
        "submissionLocked": bool(execution.get("submissionLocked")),
        "execution_status": str(execution.get("execution_status") or ""),
        "blockers": blockers,
    }
    if not (
        checks["review_ready"]
        and checks["approval_ready"]
        and checks["submission_ready"]
        and checks["submissionLocked"]
        and checks["execution_status"] == "ok"
        and not blockers
    ):
        raise AssertionError(json.dumps(checks, sort_keys=True))
    return checks


def _assert_route_shape(token: str, api_base: str, path: str, allowed_status: Iterable[str], *, timeout: int = 10) -> Dict[str, Any]:
    if path == "/observability/prometheus":
        body = _curl_text(f"{api_base.rstrip('/')}{path}", token=token, timeout=timeout)
        if "# HELP" not in body or "# TYPE" not in body:
            raise AssertionError(body[:500])
        return {"status": "ok", "data_source": "runtime", "prometheus": True}
    payload = _curl_json(f"{api_base.rstrip('/')}{path}", token=token, timeout=timeout)
    status = str(payload.get("status") or "").lower()
    if status not in {value.lower() for value in allowed_status}:
        raise AssertionError(json.dumps({"path": path, "payload": payload}, sort_keys=True))
    return payload


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Long uptime check for the LMCP backend.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8011")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="8011")
    parser.add_argument("--duration-seconds", type=int, default=120)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--health-timeout", type=int, default=60)
    parser.add_argument("--no-start-backend", action="store_true", help="Monitor an already-running backend instead of starting one.")
    args = parser.parse_args(argv)

    backend = None
    started_backend = False

    def _cleanup_backend() -> None:
        nonlocal started_backend
        if not started_backend:
            return
        started_backend = False
        try:
            assert backend is not None
            backend.terminate()
            backend.wait(timeout=5)
        except Exception:
            try:
                assert backend is not None
                backend.kill()
                backend.wait(timeout=5)
            except Exception:
                pass

    try:
        if not args.no_start_backend:
            backend = _start_backend(args.host, args.port)
            started_backend = True

        health = {"status": "unhealthy"}
        deadline = time.monotonic() + args.health_timeout
        while time.monotonic() < deadline:
            try:
                health = _curl_json(f"{args.api_base.rstrip('/')}/health", timeout=3)
            except Exception:
                health = {"status": "unhealthy"}
            if str(health.get("status", "")).lower() == "healthy":
                break
            time.sleep(1)
        if str(health.get("status", "")).lower() != "healthy":
            raise RuntimeError(json.dumps({"status": "unhealthy", "health": health}, sort_keys=True))
    except Exception:
        _cleanup_backend()
        raise

    bootstrap = {"status": "healthy", "health_url": f"{args.api_base.rstrip('/')}/health"}
    token = _login(args.api_base)

    print(json.dumps({"bootstrap": bootstrap.get("status"), "health_url": bootstrap.get("health_url")}, sort_keys=True))
    start = time.monotonic()
    cycle = 0
    last_result: Dict[str, Any] = {}
    route_timeouts = {
        "/telemetry/dashboard": 20,
        "/telemetry/source-health": 15,
        "/telemetry/review-queue": 15,
        "/operations/runtime-metrics?limit=10": 20,
        "/observability/uptime": 15,
        "/observability/prometheus": 15,
    }
    while time.monotonic() - start <= args.duration_seconds:
        cycle += 1
        cycle_start = time.monotonic()
        health = _curl_json(f"{args.api_base.rstrip('/')}/health", timeout=5)
        paper = _assert_paper(token, args.api_base)
        dashboard = _assert_route_shape(token, args.api_base, "/telemetry/dashboard", {"ok", "degraded", "healthy", "failing"}, timeout=route_timeouts["/telemetry/dashboard"])
        source = _assert_route_shape(token, args.api_base, "/telemetry/source-health", {"ok", "degraded", "healthy", "failing"}, timeout=route_timeouts["/telemetry/source-health"])
        queue = _assert_route_shape(token, args.api_base, "/telemetry/review-queue", {"ok", "degraded", "healthy", "failing"}, timeout=route_timeouts["/telemetry/review-queue"])
        runtime = _assert_route_shape(token, args.api_base, "/operations/runtime-metrics?limit=10", {"ok", "degraded", "healthy", "failing"}, timeout=route_timeouts["/operations/runtime-metrics?limit=10"])
        uptime = _assert_route_shape(token, args.api_base, "/observability/uptime", {"ok", "degraded", "healthy", "failing"}, timeout=route_timeouts["/observability/uptime"])
        prom = _assert_route_shape(token, args.api_base, "/observability/prometheus", {"ok"}, timeout=route_timeouts["/observability/prometheus"])
        last_result = {
            "cycle": cycle,
            "elapsed_seconds": round(time.monotonic() - cycle_start, 2),
            "health": health.get("status"),
            "paper": paper,
            "dashboard": dashboard.get("status"),
            "source": source.get("status"),
            "queue": queue.get("status"),
            "runtime": runtime.get("status"),
            "uptime": uptime.get("status"),
            "prometheus": prom.get("prometheus", True),
        }
        print(json.dumps(last_result, sort_keys=True))
        if time.monotonic() - start > args.duration_seconds:
            break
        time.sleep(max(1, args.interval_seconds))

    print(json.dumps({"result": "ok", "cycles": cycle, "last_result": last_result}, sort_keys=True))
    _cleanup_backend()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
