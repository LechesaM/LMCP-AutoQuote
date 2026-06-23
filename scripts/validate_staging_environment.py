#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT_DIR / ".env.staging"
FALLBACK_ENV_FILE = ROOT_DIR / ".env.staging.example"
COMPOSE_FILE = ROOT_DIR / "docker-compose.staging.yml"
APP_MAIN_FILE = ROOT_DIR / "app" / "main.py"


@dataclass
class CheckResult:
    level: str
    name: str
    message: str
    remediation: str = ""


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


def _load_staging_env() -> Tuple[Path, Dict[str, str]]:
    if DEFAULT_ENV_FILE.exists():
        return DEFAULT_ENV_FILE, _load_env_file(DEFAULT_ENV_FILE)
    return FALLBACK_ENV_FILE, _load_env_file(FALLBACK_ENV_FILE)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("FAIL", name, fail_message, remediation)


def _warn(condition: bool, name: str, warn_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("WARN", name, warn_message, remediation)
    return CheckResult("PASS", name, "ok")


def _validate_env_vars(env: Dict[str, str]) -> List[CheckResult]:
    required = [
        "LMCP_ENV",
        "LMCP_PRODUCTION_MODE",
        "LMCP_DEPLOYMENT_PROFILE",
        "LMCP_ALLOW_DEGRADED_STARTUP",
        "LMCP_ALLOW_FINAL_AUTOMATION",
        "LMCP_ENABLE_LEGACY_ROUTERS",
        "LMCP_OBSERVABILITY_ENABLED",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "LMCP_DATABASE_URL",
        "DATABASE_URL",
        "REDIS_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "LMCP_DB_BACKEND",
        "LMCP_QUEUE_BACKEND",
        "LMCP_PROJECT_ROOT",
        "LMCP_RUNTIME_DIR",
        "LMCP_LOG_DIR",
        "LMCP_HEALTH_DIR",
        "LMCP_EXPORTS_DIR",
        "LMCP_TEMP_DIR",
        "LMCP_BACKUPS_DIR",
        "LMCP_AUDIT_TRAIL_DIR",
        "LMCP_SUBMISSION_HISTORY_DIR",
        "LMCP_LOCKS_DIR",
        "LMCP_SUBMISSION_PROOFS_DIR",
        "LMCP_PORTAL_SUBMISSION_DIR",
        "LMCP_FINAL_SUBMISSION_DIR",
        "LMCP_PROOF_CENTER_DIR",
        "LMCP_OPERATOR_AUTH_DIR",
        "LMCP_OPERATOR_AUTH_DB_PATH",
        "LMCP_HANDWRITING_RUNTIME_DIR",
        "LMCP_TENDER_FORM_RUNTIME_DIR",
        "LMCP_CLICKABLE_NAVIGATION_RUNTIME_DIR",
        "PORTAL_ISOLATION_ENABLED",
        "PORTAL_ISOLATION_STATE_FILE",
        "PORTAL_ISOLATION_FAILURE_THRESHOLD",
        "PORTAL_ISOLATION_MINUTES",
        "LMCP_APP_ENTRYPOINT",
        "LMCP_BACKEND_URL",
        "LMCP_FRONTEND_URL",
        "LMCP_BACKEND_HOST_PORT",
        "LMCP_FRONTEND_HOST_PORT",
        "LMCP_POSTGRES_HOST_PORT",
        "LMCP_REDIS_HOST_PORT",
        "LMCP_PROMETHEUS_HOST_PORT",
        "LMCP_GRAFANA_HOST_PORT",
    ]
    missing = [name for name in required if name not in env]
    results = [
        _check(
            not missing,
            "required environment variables",
            "all required staging variables are present",
            f"missing required variables: {', '.join(missing)}",
            "Populate the missing keys in .env.staging or .env.staging.example.",
        )
    ]
    return results


def _validate_isolation(env: Dict[str, str], env_file: Path, compose_text: str, app_main_text: str) -> List[CheckResult]:
    results: List[CheckResult] = []

    db_urls = [env.get("LMCP_DATABASE_URL", ""), env.get("DATABASE_URL", "")]
    db_ok = all(
        url.startswith("postgresql://") and "lmcp_staging" in url and "@postgres:5432/" in url and "production" not in url.lower()
        for url in db_urls
    )
    results.append(
        _check(
            db_ok,
            "staging DB isolation",
            "database URLs point at isolated staging PostgreSQL",
            "database URLs are not isolated to staging PostgreSQL",
            "Set LMCP_DATABASE_URL and DATABASE_URL to the staging PostgreSQL service and database name.",
        )
    )

    redis_urls = [env.get("REDIS_URL", ""), env.get("CELERY_BROKER_URL", ""), env.get("CELERY_RESULT_BACKEND", "")]
    redis_ok = all(url == "redis://redis:6379/0" for url in redis_urls)
    results.append(
        _check(
            redis_ok,
            "staging Redis isolation",
            "queue URLs point at the staging Redis service",
            "queue URLs do not point at the isolated staging Redis service",
            "Set REDIS_URL, CELERY_BROKER_URL, and CELERY_RESULT_BACKEND to redis://redis:6379/0.",
        )
    )

    runtime_prefixes = [
        "LMCP_RUNTIME_DIR",
        "LMCP_MONTHLY_QUOTES_DIR",
        "LMCP_LOG_DIR",
        "LMCP_HEALTH_DIR",
        "LMCP_EXPORTS_DIR",
        "LMCP_TEMP_DIR",
        "LMCP_BACKUPS_DIR",
        "LMCP_AUDIT_TRAIL_DIR",
        "LMCP_SUBMISSION_HISTORY_DIR",
        "LMCP_LOCKS_DIR",
        "LMCP_SUBMISSION_PROOFS_DIR",
        "LMCP_PORTAL_SUBMISSION_DIR",
        "LMCP_FINAL_SUBMISSION_DIR",
        "LMCP_PROOF_CENTER_DIR",
        "LMCP_OPERATOR_AUTH_DIR",
        "LMCP_OPERATOR_AUTH_DB_PATH",
        "LMCP_HANDWRITING_RUNTIME_DIR",
        "LMCP_TENDER_FORM_RUNTIME_DIR",
        "LMCP_CLICKABLE_NAVIGATION_RUNTIME_DIR",
        "PORTAL_ISOLATION_STATE_FILE",
    ]
    runtime_ok = all(env.get(name, "").startswith("/app/runtime/staging") for name in runtime_prefixes)
    results.append(
        _check(
            runtime_ok,
            "runtime storage isolation",
            "runtime artifacts are scoped to /app/runtime/staging",
            "one or more runtime artifact paths escape the staging runtime directory",
            "Move all staging runtime paths under /app/runtime/staging.",
        )
    )

    telemetry_ok = env.get("LMCP_OBSERVABILITY_ENABLED") == "1" and "prometheus:" in compose_text and "grafana:" in compose_text
    results.append(
        _check(
            telemetry_ok,
            "telemetry configuration presence",
            "telemetry is enabled and staging telemetry services are declared",
            "telemetry settings or services are missing",
            "Keep LMCP_OBSERVABILITY_ENABLED=1 and ensure Prometheus/Grafana services remain declared.",
        )
    )

    endpoint_ok = "app.main:app" in env.get("LMCP_APP_ENTRYPOINT", "") and '"/health"' in app_main_text and '"/status"' in app_main_text
    results.append(
        _check(
            endpoint_ok,
            "health/status endpoint configuration",
            "backend entrypoint and health/status routes are configured",
            "backend entrypoint or health/status routes are missing",
            "Keep LMCP_APP_ENTRYPOINT on app.main:app and preserve /health and /status in app/main.py.",
        )
    )

    dry_run_ok = env.get("LMCP_ALLOW_FINAL_AUTOMATION") == "false" and env.get("PORTAL_ISOLATION_ENABLED") == "true"
    results.append(
        _check(
            dry_run_ok,
            "dry-run enforcement",
            "dry-run protection is enabled by default",
            "dry-run protection is not explicitly enabled",
            "Set LMCP_ALLOW_FINAL_AUTOMATION=false and PORTAL_ISOLATION_ENABLED=true.",
        )
    )

    final_automation_disabled = env.get("LMCP_ALLOW_FINAL_AUTOMATION") == "false" and env.get("STRICT_PRODUCTION_STARTUP") == "0"
    results.append(
        _check(
            final_automation_disabled,
            "final automation disabled",
            "final automation remains disabled in staging",
            "final automation is not disabled in staging",
            "Keep LMCP_ALLOW_FINAL_AUTOMATION=false and STRICT_PRODUCTION_STARTUP=0 in staging.",
        )
    )

    no_prod_db = all("production" not in env.get(name, "").lower() and "lmcp:lmcp@" not in env.get(name, "") for name in ("LMCP_DATABASE_URL", "DATABASE_URL"))
    results.append(
        _check(
            no_prod_db,
            "no production DB URLs",
            "staging config does not reference production database URLs",
            "a production database URL pattern was detected",
            "Replace any production database URL with the staging PostgreSQL URL.",
        )
    )

    no_prod_queue = all("production" not in env.get(name, "").lower() and "localhost" not in env.get(name, "").lower() for name in ("REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"))
    results.append(
        _check(
            no_prod_queue,
            "no production queue hosts",
            "staging queue URLs do not target production hosts",
            "a production or localhost queue host was detected",
            "Point all queue URLs at the isolated staging Redis service.",
        )
    )

    no_prod_creds = all("production" not in env.get(name, "").lower() for name in ("LMCP_OPERATOR_AUTH_DB_PATH", "LMCP_RUNTIME_DIR", "PORTAL_ISOLATION_STATE_FILE"))
    results.append(
        _check(
            no_prod_creds,
            "no production credential paths",
            "credential and runtime paths are staging-scoped",
            "a production credential or runtime path was detected",
            "Move credential and runtime paths under /app/runtime/staging.",
        )
    )

    backend_ok = "uvicorn" in compose_text and "app.main:app" in compose_text and "/health" in compose_text
    results.append(
        _warn(
            not backend_ok,
            "backend command and healthcheck",
            "backend command or healthcheck does not match the expected staging pattern",
            "Keep the backend command on uvicorn app.main:app and the healthcheck on /health.",
        )
    )

    return results


def _validate_compose_services(compose_text: str) -> List[CheckResult]:
    required_services = ["backend:", "frontend:", "worker:", "operations-worker:", "beat:", "postgres:", "redis:", "prometheus:", "grafana:"]
    missing = [service.rstrip(":") for service in required_services if service not in compose_text]
    return [
        _check(
            not missing,
            "required staging services",
            "all required staging services are declared",
            f"missing staging services: {', '.join(missing)}",
            "Add the missing services to docker-compose.staging.yml.",
        )
    ]


def run_validation() -> List[CheckResult]:
    env_path, env = _load_staging_env()
    compose_text = _text(COMPOSE_FILE)
    app_main_text = _text(APP_MAIN_FILE)

    results: List[CheckResult] = []
    results.extend(_validate_env_vars(env))
    results.extend(_validate_compose_services(compose_text))
    results.extend(_validate_isolation(env, env_path, compose_text, app_main_text))

    # Lightweight content checks that should not fail the bootstrap, but should be visible.
    manifest_uses_example = ".env.staging.example" in compose_text
    results.append(
        _warn(
            not manifest_uses_example,
            "manifest env source",
            "compose manifest does not explicitly reference .env.staging.example",
            "Keep docker-compose.staging.yml wired to the checked-in staging example file.",
        )
    )

    return results


def _print_results(results: List[CheckResult]) -> int:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for result in results:
        counts[result.level] += 1

    print(f"PASS: {counts['PASS']}  WARN: {counts['WARN']}  FAIL: {counts['FAIL']}")
    print("")
    for result in results:
        print(f"[{result.level}] {result.name}: {result.message}")
        if result.level != "PASS" and result.remediation:
            print(f"  Remediation: {result.remediation}")
    print("")
    if counts["FAIL"]:
        print("Staging environment validation failed.")
        return 1
    if counts["WARN"]:
        print("Staging environment validation passed with warnings.")
    else:
        print("Staging environment validation passed.")
    return 0


def main() -> int:
    results = run_validation()
    return _print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())

