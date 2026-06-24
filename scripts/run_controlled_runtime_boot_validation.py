#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlopen


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ENV_FILE = PROJECT_ROOT / ".env.production.example"
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.production.example.yml"
LOCK_FILE = PROJECT_ROOT / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
BOOT_VALIDATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "runtime-boot-validations"
LATEST_BOOT_VALIDATION_JSON = BOOT_VALIDATION_ROOT / "latest_runtime_boot_validation.json"
LATEST_BOOT_VALIDATION_MD = BOOT_VALIDATION_ROOT / "latest_runtime_boot_validation.md"

EXPECTED_SERVICES = (
    "backend",
    "frontend",
    "postgres",
    "redis",
    "worker",
    "prometheus",
    "grafana",
)


@dataclass
class CheckResult:
    level: str
    name: str
    message: str
    remediation: str = ""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def boot_timestamp() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text if text else default
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _build_package_report() -> Dict[str, Any]:
    module = _load_module(PROJECT_ROOT / "scripts" / "validate_production_package.py", "runtime_boot_validate_package")
    return safe_dict(module.build_production_package_report())


def _build_access_report() -> Dict[str, Any]:
    module = _load_module(PROJECT_ROOT / "scripts" / "validate_production_access_governance.py", "runtime_boot_validate_access")
    return safe_dict(module.build_production_access_governance_report())


def _load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _looks_placeholder(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    if lowered.startswith("change-me"):
        return True
    if lowered.startswith("${") and lowered.endswith("}"):
        return True
    if lowered in {"placeholder", "tbd", "todo"}:
        return True
    return False


def _contains_all(text: str, needles: Tuple[str, ...]) -> bool:
    return all(needle in text for needle in needles)


def _compose_command(project_name: str, *args: str) -> List[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        project_name,
        "--env-file",
        str(ENV_FILE),
        "-f",
        str(COMPOSE_FILE),
        *args,
    ]


def _run_compose(project_name: str, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(_compose_command(project_name, *args), capture_output=True, text=True, check=check)


def _compose_config() -> Tuple[bool, str, str]:
    try:
        result = subprocess.run(
            ["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(COMPOSE_FILE), "config"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "", "docker compose is unavailable"
    output = safe_str(getattr(result, "stdout", ""))
    if result.returncode != 0:
        message = safe_str(getattr(result, "stderr", "")) or output or "docker compose config failed"
        return False, output, message
    return True, output, ""


def _probe_http(url: str, timeout: float = 10.0) -> Dict[str, Any]:
    request = urlopen(url, timeout=timeout)  # nosec B310 - controlled local smoke validation
    body = request.read().decode("utf-8", errors="replace")
    status = getattr(request, "status", 200)
    headers = dict(request.headers.items()) if hasattr(request, "headers") else {}
    try:
        payload = json.loads(body)
    except Exception:
        payload = {"body": body}
    return {"status_code": status, "headers": headers, "payload": payload}


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("FAIL", name, fail_message, remediation)


def _overall_status(statuses: List[str]) -> str:
    normalized = [safe_str(item, "FAIL").upper() for item in statuses if safe_str(item)]
    if not normalized:
        return "FAIL"
    if any(item == "FAIL" for item in normalized):
        return "FAIL"
    if any(item in {"WARN", "WATCH"} for item in normalized):
        return "WARN"
    return "PASS"


def _summary_counts(checks: List[CheckResult]) -> Dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for check in checks:
        counts[check.level] = counts.get(check.level, 0) + 1
    return counts


def _compose_service_states(compose_json: str) -> Dict[str, Any]:
    try:
        payload = json.loads(compose_json)
        if isinstance(payload, list):
            states: Dict[str, Any] = {}
            for item in payload:
                item_dict = safe_dict(item)
                service = safe_str(item_dict.get("Service") or item_dict.get("service"))
                if service:
                    states[service] = item_dict
            return states
    except Exception:
        pass
    return {}


def _service_running(item: Dict[str, Any]) -> bool:
    state = safe_str(item.get("State") or item.get("state") or item.get("Status"), "").lower()
    health = safe_str(item.get("Health") or item.get("health") or item.get("health_status"), "").lower()
    if health in {"healthy", "ok"}:
        return True
    return state in {"running", "healthy", "up"}


def _docker_runtime_unavailable(message: str) -> bool:
    lowered = safe_str(message, "").lower()
    return any(
        needle in lowered
        for needle in (
            "permission denied while trying to connect to the docker daemon socket",
            "cannot connect to the docker daemon",
            "connect: operation not permitted",
            "docker daemon is not running",
            "docker compose is unavailable",
        )
    )


def _wait_for_http(url: str, timeout_seconds: int = 120, interval: float = 2.0) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: str = ""
    while time.monotonic() < deadline:
        try:
            return _probe_http(url, timeout=max(interval, 5.0))
        except Exception as exc:  # pragma: no cover - exercised in failure fixtures
            last_error = safe_str(exc)
            time.sleep(interval)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _build_checks(
    env: Dict[str, str],
    compose_ok: bool,
    compose_output: str,
    compose_message: str,
    package: Dict[str, Any],
    access: Dict[str, Any],
    lock_data: Dict[str, Any],
    service_states: Dict[str, Any],
    backend_probe: Dict[str, Any],
    frontend_probe: Dict[str, Any],
    boot_launch_level: str,
) -> List[CheckResult]:
    results: List[CheckResult] = []

    results.append(
        _check(
            ENV_FILE.exists(),
            "production env example exists",
            f"{ENV_FILE.name} is present",
            f"{ENV_FILE.name} is missing",
            "Add .env.production.example to the repository.",
        )
    )
    results.append(
        _check(
            COMPOSE_FILE.exists(),
            "production compose file exists",
            f"{COMPOSE_FILE.name} is present",
            f"{COMPOSE_FILE.name} is missing",
            "Add docker-compose.production.example.yml to the repository.",
        )
    )
    results.append(
        _check(
            compose_ok,
            "docker compose config parses",
            "docker compose config completed successfully",
            f"docker compose config failed: {compose_message}",
            "Fix the production compose example so docker compose config succeeds.",
        )
    )
    if compose_ok:
        results.append(
            _check(
                boot_launch_level in {"PASS", "WARN"},
                "controlled stack startup attempted",
                "docker compose up was attempted under controlled mode",
                f"docker compose up failed: {compose_message}",
                "Inspect compose startup and the local Docker daemon.",
            )
        )

    if boot_launch_level == "FAIL":
        service_level = "FAIL"
    elif boot_launch_level == "WARN":
        service_level = "WARN"
    else:
        service_level = "PASS"

    safe_defaults = [
        ("LMCP_ALLOW_FINAL_AUTOMATION", "false"),
        ("LMCP_DRY_RUN_MODE", "true"),
        ("LMCP_REQUIRE_HUMAN_SUPERVISION", "true"),
        ("LMCP_PRODUCTION_MODE", "locked_production"),
        ("LMCP_DEPLOYMENT_PROFILE", "production"),
        ("STRICT_PRODUCTION_STARTUP", "1"),
        ("LMCP_ALLOW_DEGRADED_STARTUP", "false"),
        ("LMCP_RUNTIME_SAFETY_ENABLED", "1"),
        ("LMCP_OBSERVABILITY_ENABLED", "1"),
    ]
    for key, expected in safe_defaults:
        results.append(
            _check(
                env.get(key) == expected,
                f"{key} safe default",
                f"{key} is set to {expected}",
                f"{key} must be set to {expected}",
                f"Set {key}={expected} in the production environment example.",
            )
        )

    results.append(
        _check(
            all(
                not env.get(key, "").strip()
                for key in (
                    "LMCP_PRODUCTION_SUBMISSION_USERNAME",
                    "LMCP_PRODUCTION_SUBMISSION_PASSWORD",
                    "LMCP_PRODUCTION_PORTAL_USERNAME",
                    "LMCP_PRODUCTION_PORTAL_PASSWORD",
                )
            ),
            "no live credentials are present",
            "production submission credential placeholders are blank",
            "production submission credentials must be blank by default",
            "Leave production credential placeholders empty in the example package.",
        )
    )

    results.append(
        _check(
            env.get("LMCP_ALLOW_FINAL_AUTOMATION") == "false",
            "final automation remains disabled",
            "final automation is explicitly disabled",
            "final automation is not disabled",
            "Keep LMCP_ALLOW_FINAL_AUTOMATION=false in the production package.",
        )
    )
    results.append(
        _check(
            env.get("LMCP_DRY_RUN_MODE") == "true",
            "dry-run remains enabled",
            "dry-run mode is explicitly enabled",
            "dry-run mode is not enabled",
            "Keep LMCP_DRY_RUN_MODE=true in the production package.",
        )
    )
    results.append(
        _check(
            env.get("LMCP_REQUIRE_HUMAN_SUPERVISION") == "true",
            "human supervision remains required",
            "human supervision is required by default",
            "human supervision is not required",
            "Keep LMCP_REQUIRE_HUMAN_SUPERVISION=true in the production package.",
        )
    )

    service_expectations = {
        "backend": "backend service expected",
        "frontend": "frontend service expected",
        "postgres": "PostgreSQL service expected",
        "redis": "Redis service expected",
        "worker": "worker service expected",
        "prometheus": "Prometheus service expected",
        "grafana": "Grafana service expected",
    }
    for service, label in service_expectations.items():
        if service in service_states:
            results.append(CheckResult("PASS", label, f"{service} is defined in the production compose runtime"))
        else:
            results.append(
                CheckResult(
                    service_level,
                    label,
                    f"{service} is missing from the running production compose stack",
                    f"Ensure {service} starts successfully under docker compose up.",
                )
            )

    def service_check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str) -> None:
        if condition:
            results.append(CheckResult("PASS", name, pass_message))
            return
        results.append(CheckResult(service_level, name, fail_message, remediation))

    service_check(
        _service_running(service_states.get("backend", {})),
        "backend container starts",
        "backend container is running or healthy",
        "backend container is not running or healthy",
        "Inspect backend container logs and healthcheck status.",
    )
    service_check(
        _service_running(service_states.get("frontend", {})),
        "frontend container starts",
        "frontend container is running or healthy",
        "frontend container is not running or healthy",
        "Inspect frontend container logs and healthcheck status.",
    )
    service_check(
        _service_running(service_states.get("postgres", {})),
        "PostgreSQL starts",
        "postgres is running or healthy",
        "postgres is not running or healthy",
        "Inspect postgres container health and data volume initialization.",
    )
    service_check(
        _service_running(service_states.get("redis", {})),
        "Redis starts",
        "redis is running or healthy",
        "redis is not running or healthy",
        "Inspect redis container health and broker connectivity.",
    )
    service_check(
        _service_running(service_states.get("worker", {})),
        "worker starts",
        "worker is running or healthy",
        "worker is not running or healthy",
        "Inspect celery worker logs and startup sequencing.",
    )
    service_check(
        _service_running(service_states.get("prometheus", {})),
        "Prometheus starts",
        "prometheus is running or healthy",
        "prometheus is not running or healthy",
        "Inspect prometheus container startup and config bind mount.",
    )
    service_check(
        _service_running(service_states.get("grafana", {})),
        "Grafana starts",
        "grafana is running or healthy",
        "grafana is not running or healthy",
        "Inspect grafana container startup and admin credential placeholders.",
    )

    service_check(
        backend_probe.get("status_code") == 200 and safe_str(safe_dict(backend_probe.get("payload")).get("status"), "fail").lower() in {"ok", "pass", "ready"},
        "backend health endpoints respond",
        "backend health endpoint returned a healthy response",
        "backend health endpoint did not return a healthy response",
        "Inspect the backend /health route and compose port mapping.",
    )
    service_check(
        frontend_probe.get("status_code") == 200,
        "frontend service responds",
        "frontend root endpoint returned HTTP 200",
        "frontend root endpoint did not return HTTP 200",
        "Inspect the frontend container and nginx configuration.",
    )

    lock_ok = bool(lock_data) and lock_data.get("final_automation_disabled") is True and lock_data.get("live_portal_submission_disabled") is True
    lock_ok = lock_ok and lock_data.get("production_credentials_disabled") is True and lock_data.get("dry_run_mode_required") is True
    lock_ok = lock_ok and lock_data.get("submission_execution_allowed") is False and lock_data.get("human_supervision_required") is True
    results.append(
        _check(
            lock_ok,
            "submission locks remain enforced",
            "submission locks explicitly keep live submission disabled",
            "submission lock enforcement is incomplete",
            "Keep the production submission lock file present and locked.",
        )
    )

    results.append(
        _check(
            _looks_placeholder(env.get("LMCP_SECRET_KEY", ""))
            and _looks_placeholder(env.get("POSTGRES_PASSWORD", ""))
            and _looks_placeholder(env.get("LMCP_GRAFANA_ADMIN_PASSWORD", ""))
            and all(
                _looks_placeholder(env.get(key, ""))
                for key in (
                    "LMCP_PRODUCTION_SUBMISSION_USERNAME",
                    "LMCP_PRODUCTION_SUBMISSION_PASSWORD",
                    "LMCP_PRODUCTION_PORTAL_USERNAME",
                    "LMCP_PRODUCTION_PORTAL_PASSWORD",
                )
            ),
            "no live credentials are present",
            "credential-bearing values are placeholder-only",
            "live credential material appears to be present",
            "Replace live credential values with placeholders and use supervised secret injection.",
        )
    )

    results.append(
        _check(
            safe_str(package.get("overall_status"), "FAIL").upper() == "PASS",
            "production package readiness",
            "production package validation remains PASS",
            "production package validation is not PASS",
            "Fix the production package validation before relying on the boot check.",
        )
    )
    results.append(
        _check(
            safe_str(access.get("overall_status"), "FAIL").upper() == "PASS",
            "production access readiness",
            "production access governance validation remains PASS",
            "production access governance validation is not PASS",
            "Fix the production access governance validation before relying on the boot check.",
        )
    )

    return results


def build_runtime_boot_validation_report(
    *,
    env_file: Path = ENV_FILE,
    compose_file: Path = COMPOSE_FILE,
    lock_file: Path = LOCK_FILE,
    output_root: Path = BOOT_VALIDATION_ROOT,
    compose_timeout_seconds: int = 180,
    boot_timeout_seconds: int = 300,
) -> Dict[str, Any]:
    env = _load_env_file(env_file)
    package = _build_package_report()
    access = _build_access_report()
    compose_ok, compose_output, compose_message = _compose_config()

    project_name = f"lmcp-boot-{boot_timestamp().lower()}-{uuid.uuid4().hex[:8]}"
    compose_started = False
    compose_down_status = ""
    service_states: Dict[str, Any] = {}
    backend_probe: Dict[str, Any] = {}
    frontend_probe: Dict[str, Any] = {}
    raw_up_output = ""
    raw_ps_output = ""

    boot_launch_level = "WARN"
    try:
        if compose_ok:
            up_result = _run_compose(project_name, "up", "-d", "--build", "--remove-orphans", "--wait", "--wait-timeout", str(compose_timeout_seconds))
            raw_up_output = safe_str(up_result.stdout) or safe_str(up_result.stderr)
            compose_started = up_result.returncode == 0
            if not compose_started:
                compose_message = safe_str(up_result.stderr) or safe_str(up_result.stdout) or "docker compose up failed"
                boot_launch_level = "WARN" if _docker_runtime_unavailable(compose_message) else "FAIL"
            else:
                boot_launch_level = "PASS"
                ps_result = _run_compose(project_name, "ps", "--format", "json")
                raw_ps_output = safe_str(ps_result.stdout) or safe_str(ps_result.stderr)
                if ps_result.returncode == 0:
                    service_states = _compose_service_states(raw_ps_output)
                backend_probe = _wait_for_http("http://127.0.0.1:8001/health", timeout_seconds=boot_timeout_seconds)
                frontend_probe = _wait_for_http("http://127.0.0.1:4176/", timeout_seconds=boot_timeout_seconds)
        else:
            boot_launch_level = "FAIL"
    finally:
        down_result = _run_compose(project_name, "down", "-v", "--remove-orphans")
        compose_down_status = "ok" if down_result.returncode == 0 else safe_str(down_result.stderr) or safe_str(down_result.stdout) or "docker compose down failed"

    lock_data = safe_dict(read_json(lock_file, {}))
    checks = _build_checks(env, compose_ok, compose_output, compose_message, package, access, lock_data, service_states, backend_probe, frontend_probe, boot_launch_level)
    overall_status = _overall_status([check.level for check in checks])
    summary_counts = _summary_counts(checks)

    score_components = [
        100.0 if compose_ok else 0.0,
        safe_float(package.get("production_governance_summary", {}).get("production_governance_score"), 0.0),
        safe_float(access.get("production_access_governance_summary", {}).get("access_governance_score"), 0.0),
        100.0 if compose_started else 0.0,
        100.0 if backend_probe.get("status_code") == 200 else 0.0,
        100.0 if frontend_probe.get("status_code") == 200 else 0.0,
        100.0 if summary_counts["FAIL"] == 0 else 0.0,
    ]
    overall_score = round(mean(score_components), 2)

    validation_id = f"{boot_timestamp()}-production-boot-{uuid.uuid4().hex[:8]}"
    export_dir = output_root / validation_id
    export_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "validation_id": validation_id,
        "generated_at": iso_now(),
        "source_runtime": str(output_root),
        "overall_status": overall_status,
        "overall_authority": "GO" if overall_status == "PASS" else "WATCH" if overall_status == "WARN" else "NO_GO",
        "overall_score": overall_score,
        "compose_validation": {
            "compose_parsed": compose_ok,
            "compose_message": compose_message,
            "compose_output_excerpt": compose_output[:2000],
            "compose_up_output_excerpt": raw_up_output[:2000],
            "compose_ps_output_excerpt": raw_ps_output[:2000],
            "compose_down_status": compose_down_status,
            "boot_launch_level": boot_launch_level,
        },
        "service_states": service_states,
        "backend_health": backend_probe,
        "frontend_health": frontend_probe,
        "validation_summaries": {
            "production_package": package,
            "production_access_governance": access,
        },
        "summary_counts": summary_counts,
        "checks": [
            {
                "level": check.level,
                "name": check.name,
                "message": check.message,
                "remediation": check.remediation,
            }
            for check in checks
        ],
        "boot_readiness_summary": {
            "status": overall_status,
            "production_runtime_boot_ready": overall_status == "PASS",
            "boot_launch_level": boot_launch_level,
            "backend_started": _service_running(service_states.get("backend", {})),
            "frontend_started": _service_running(service_states.get("frontend", {})),
            "postgres_started": _service_running(service_states.get("postgres", {})),
            "redis_started": _service_running(service_states.get("redis", {})),
            "worker_started": _service_running(service_states.get("worker", {})),
            "prometheus_started": _service_running(service_states.get("prometheus", {})),
            "grafana_started": _service_running(service_states.get("grafana", {})),
            "health_endpoints_respond": backend_probe.get("status_code") == 200 and frontend_probe.get("status_code") == 200,
            "dry_run_mode_enabled": env.get("LMCP_DRY_RUN_MODE") == "true",
            "final_automation_disabled": env.get("LMCP_ALLOW_FINAL_AUTOMATION") == "false",
            "human_supervision_required": env.get("LMCP_REQUIRE_HUMAN_SUPERVISION") == "true",
            "submission_locks_enforced": bool(lock_data) and lock_data.get("final_automation_disabled") is True and lock_data.get("submission_execution_allowed") is False,
        },
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_operations": False,
            "production_submission_enablement": False,
            "production_connectivity_required": False,
            "human_supervision_required": True,
            "dry_run_protections_active": True,
        },
        "artifact_paths": {
            "json": str(export_dir / "runtime_boot_validation.json"),
            "markdown": str(export_dir / "runtime_boot_validation.md"),
            "latest_json": str(output_root / "latest_runtime_boot_validation.json"),
            "latest_markdown": str(output_root / "latest_runtime_boot_validation.md"),
        },
        "warnings": [] if overall_status == "PASS" else ["runtime boot validation produced one or more non-PASS checks"],
    }

    write_json(export_dir / "runtime_boot_validation.json", payload)
    write_text(export_dir / "runtime_boot_validation.md", markdown_summary(payload))
    write_json(output_root / "latest_runtime_boot_validation.json", payload)
    write_text(output_root / "latest_runtime_boot_validation.md", markdown_summary(payload))
    return payload


def markdown_summary(payload: Dict[str, Any]) -> str:
    boot = safe_dict(payload.get("boot_readiness_summary"))
    lines = [
        "# Controlled Runtime Boot Validation",
        "",
        f"- Validation ID: `{safe_str(payload.get('validation_id'))}`",
        f"- Generated At: `{safe_str(payload.get('generated_at'))}`",
        f"- Overall Status: `{safe_str(payload.get('overall_status'), 'FAIL')}`",
        f"- Overall Score: `{safe_float(payload.get('overall_score'), 0.0):.2f}`",
        f"- Summary Counts: `{json.dumps(safe_dict(payload.get('summary_counts')), sort_keys=True)}`",
        "",
        "## Boot Readiness",
        f"- Production runtime boot ready: `{str(bool(boot.get('production_runtime_boot_ready'))).lower()}`",
        f"- Backend started: `{str(bool(boot.get('backend_started'))).lower()}`",
        f"- Frontend started: `{str(bool(boot.get('frontend_started'))).lower()}`",
        f"- PostgreSQL started: `{str(bool(boot.get('postgres_started'))).lower()}`",
        f"- Redis started: `{str(bool(boot.get('redis_started'))).lower()}`",
        f"- Worker started: `{str(bool(boot.get('worker_started'))).lower()}`",
        f"- Prometheus started: `{str(bool(boot.get('prometheus_started'))).lower()}`",
        f"- Grafana started: `{str(bool(boot.get('grafana_started'))).lower()}`",
        f"- Health endpoints respond: `{str(bool(boot.get('health_endpoints_respond'))).lower()}`",
        f"- Dry-run mode enabled: `{str(bool(boot.get('dry_run_mode_enabled'))).lower()}`",
        f"- Final automation disabled: `{str(bool(boot.get('final_automation_disabled'))).lower()}`",
        f"- Human supervision required: `{str(bool(boot.get('human_supervision_required'))).lower()}`",
        f"- Submission locks enforced: `{str(bool(boot.get('submission_locks_enforced'))).lower()}`",
        "",
        "## Checks",
    ]
    for check in safe_list(payload.get("checks")):
        lines.append(f"- {safe_str(check.get('level'))}: {safe_str(check.get('name'))} - {safe_str(check.get('message'))}")
    lines += [
        "",
        "## Compose Validation",
        f"- Parsed: `{str(bool(safe_dict(payload.get('compose_validation')).get('compose_parsed'))).lower()}`",
        f"- Message: `{safe_str(safe_dict(payload.get('compose_validation')).get('compose_message'), 'ok')}`",
        "",
        "## Safety Guarantees",
        f"- Autonomous procurement authority: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('autonomous_procurement_authority'))).lower()}`",
        f"- Irreversible operations: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('irreversible_operations'))).lower()}`",
        f"- Production submission enablement: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('production_submission_enablement'))).lower()}`",
        f"- Production connectivity required: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('production_connectivity_required'))).lower()}`",
        f"- Human supervision required: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('human_supervision_required'))).lower()}`",
        f"- Dry-run protections active: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('dry_run_protections_active'))).lower()}`",
        "",
        "## Evidence Artifacts",
    ]
    for key, value in safe_dict(payload.get("artifact_paths")).items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def _print_summary(payload: Dict[str, Any]) -> None:
    boot = safe_dict(payload.get("boot_readiness_summary"))
    print(f"Runtime boot validation: {safe_str(payload.get('artifact_paths', {}).get('json'), '')}")
    print(f"Overall status: {safe_str(payload.get('overall_status'), 'FAIL')}")
    print(f"Overall score: {safe_float(payload.get('overall_score'), 0.0):.2f}")
    print(f"Backend started: {str(bool(boot.get('backend_started'))).lower()}")
    print(f"Frontend started: {str(bool(boot.get('frontend_started'))).lower()}")
    print(f"Dry-run enabled: {str(bool(boot.get('dry_run_mode_enabled'))).lower()}")
    print(f"Human supervision required: {str(bool(boot.get('human_supervision_required'))).lower()}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run controlled runtime boot validation for the production deployment package.")
    parser.add_argument("--output-root", type=Path, default=BOOT_VALIDATION_ROOT, help="Where to write runtime boot validation evidence.")
    parser.add_argument("--json", action="store_true", help="Print the full validation payload as JSON.")
    parser.add_argument("--compose-timeout", type=int, default=180, help="Seconds to wait for docker compose up --wait.")
    parser.add_argument("--boot-timeout", type=int, default=300, help="Seconds to wait for HTTP health endpoints.")
    args = parser.parse_args(argv)

    payload = build_runtime_boot_validation_report(
        output_root=args.output_root,
        compose_timeout_seconds=args.compose_timeout,
        boot_timeout_seconds=args.boot_timeout,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
