#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


sys.dont_write_bytecode = True

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env.production.example"
COMPOSE_FILE = ROOT_DIR / "docker-compose.production.example.yml"
LOCK_FILE = ROOT_DIR / "runtime" / "production" / "go_live_guards" / "submission_locks.json"


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


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("FAIL", name, fail_message, remediation)


def _warn(condition: bool, name: str, warn_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("WARN", name, warn_message, remediation)
    return CheckResult("PASS", name, "ok")


def _contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def _path_prefix_ok(env: Dict[str, str], keys: Iterable[str], prefix: str) -> bool:
    return all(str(env.get(key, "")).startswith(prefix) for key in keys)


def _build_checks(env: Dict[str, str], compose_text: str, lock_data: Dict[str, Any]) -> List[CheckResult]:
    results: List[CheckResult] = []

    results.append(
        _check(
            ENV_FILE.exists(),
            "production env example exists",
            f"{ENV_FILE.name} is present",
            f"{ENV_FILE.name} is missing",
            "Add a production environment example at .env.production.example.",
        )
    )
    results.append(
        _check(
            COMPOSE_FILE.exists(),
            "production compose file exists",
            f"{COMPOSE_FILE.name} is present",
            f"{COMPOSE_FILE.name} is missing",
            "Add a production compose example at docker-compose.production.example.yml.",
        )
    )

    safe_defaults = [
        ("LMCP_ENV", "production"),
        ("LMCP_PRODUCTION_MODE", "locked_production"),
        ("LMCP_DEPLOYMENT_PROFILE", "production"),
        ("STRICT_PRODUCTION_STARTUP", "1"),
        ("LMCP_ALLOW_DEGRADED_STARTUP", "false"),
        ("LMCP_ALLOW_FINAL_AUTOMATION", "false"),
        ("LMCP_DRY_RUN_MODE", "true"),
        ("LMCP_REQUIRE_HUMAN_SUPERVISION", "true"),
        ("LMCP_RUNTIME_SAFETY_ENABLED", "1"),
        ("LMCP_ENABLE_LEGACY_ROUTERS", "0"),
        ("LMCP_OBSERVABILITY_ENABLED", "1"),
        ("LMCP_SECRET_KEY", "change-me-production-secret"),
        ("LMCP_CORS_ORIGINS", "https://lmcp.example.com"),
        ("LMCP_OPERATOR_SESSION_COOKIE_SECURE", "true"),
        ("LMCP_OPERATOR_AUTH_ALLOW_DEV_FALLBACK", "false"),
        ("PORTAL_ISOLATION_ENABLED", "true"),
        ("LMCP_AUDIT_RETENTION_DAYS", "3650"),
    ]
    for key, expected in safe_defaults:
        results.append(
            _check(
                env.get(key) == expected,
                f"{key} default",
                f"{key} is set to {expected}",
                f"{key} must be set to {expected}",
                f"Set {key}={expected} in .env.production.example and the compose environment.",
            )
        )

    compose_safe_defaults = _contains_all(
        compose_text,
        (
            'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
            'LMCP_DRY_RUN_MODE: "true"',
            'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
            'LMCP_SECRET_KEY: ${LMCP_SECRET_KEY:-change-me-production-secret}',
            'LMCP_CORS_ORIGINS: ${LMCP_CORS_ORIGINS:-https://lmcp.example.com}',
            'LMCP_OPERATOR_SESSION_COOKIE_SECURE: "true"',
            'LMCP_OPERATOR_AUTH_ALLOW_DEV_FALLBACK: "false"',
        ),
    )
    results.append(
        _check(
            compose_safe_defaults,
            "compose safety defaults",
            "compose template encodes the production safety defaults",
            "compose template is missing one or more production safety defaults",
            "Keep the safe default flags in docker-compose.production.example.yml so the template remains locked down.",
        )
    )

    submission_creds_blank = all(not env.get(key, "").strip() for key in (
        "LMCP_PRODUCTION_SUBMISSION_USERNAME",
        "LMCP_PRODUCTION_SUBMISSION_PASSWORD",
        "LMCP_PRODUCTION_PORTAL_USERNAME",
        "LMCP_PRODUCTION_PORTAL_PASSWORD",
    ))
    results.append(
        _check(
            submission_creds_blank,
            "production submission credentials unset",
            "production submission credential placeholders are blank",
            "production submission credentials must be blank by default",
            "Leave production submission credential placeholders empty until a supervised deployment specifically supplies them.",
        )
    )

    results.append(
        _check(
            env.get("LMCP_SECRET_KEY") == "change-me-production-secret",
            "production secret key placeholder",
            "production secret key uses a placeholder value",
            "production secret key is missing or not the safe placeholder",
            "Keep LMCP_SECRET_KEY set to a placeholder in the example package and inject the real secret from a secret manager at deployment time.",
        )
    )

    runtime_keys = [
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
        "LMCP_MANUAL_PRODUCTION_DIR",
        "LMCP_MANUAL_PRODUCTION_DB_PATH",
        "LMCP_SUBMISSION_LOCK_FILE",
        "LMCP_OPERATOR_AUTH_DIR",
        "LMCP_OPERATOR_AUTH_DB_PATH",
        "LMCP_HANDWRITING_RUNTIME_DIR",
        "LMCP_TENDER_FORM_RUNTIME_DIR",
        "LMCP_CLICKABLE_NAVIGATION_RUNTIME_DIR",
        "PORTAL_ISOLATION_STATE_FILE",
    ]
    runtime_ok = _path_prefix_ok(env, runtime_keys, "/app/runtime/production")
    results.append(
        _check(
            runtime_ok,
            "production runtime paths separated from staging",
            "all runtime paths are production-scoped",
            "one or more runtime paths still point at staging",
            "Move every runtime path to /app/runtime/production.",
        )
    )
    results.append(
        _check(
            "/app/runtime/staging" not in compose_text and "/app/runtime/staging" not in " ".join(env.values()),
            "no staging runtime references",
            "staging runtime references are absent",
            "staging runtime references are still present",
            "Remove staging paths from the production package.",
        )
    )

    results.append(
        _check(
            env.get("LMCP_SUBMISSION_LOCK_FILE") == "/app/runtime/production/go_live_guards/submission_locks.json",
            "submission lock file required",
            "submission lock file points at the production guard path",
            "submission lock file is missing or points outside production runtime",
            "Set LMCP_SUBMISSION_LOCK_FILE to /app/runtime/production/go_live_guards/submission_locks.json.",
        )
    )

    observability_ok = _contains_all(compose_text, ("prometheus:", "grafana:"))
    results.append(
        _check(
            observability_ok,
            "observability services are defined",
            "Prometheus and Grafana services are declared",
            "Prometheus and Grafana are missing from the production compose file",
            "Keep Prometheus and Grafana defined in docker-compose.production.example.yml.",
        )
    )

    db_isolated = (
        env.get("LMCP_DATABASE_URL", "").startswith("postgresql://")
        and "@postgres:5432/" in env.get("LMCP_DATABASE_URL", "")
        and env.get("DATABASE_URL", "").startswith("postgresql://")
        and "@postgres:5432/" in env.get("DATABASE_URL", "")
        and env.get("REDIS_URL") == "redis://redis:6379/0"
        and env.get("CELERY_BROKER_URL") == "redis://redis:6379/0"
        and env.get("CELERY_RESULT_BACKEND") == "redis://redis:6379/0"
    )
    results.append(
        _check(
            db_isolated,
            "database and broker are isolated",
            "backend, database, and broker are scoped to local compose services",
            "database or broker settings are not isolated",
            "Point the production compose backend at the local postgres and redis services only.",
        )
    )

    submission_lock_ok = bool(lock_data) and (
        lock_data.get("final_automation_disabled") is True
        and lock_data.get("live_portal_submission_disabled") is True
        and lock_data.get("production_credentials_disabled") is True
        and lock_data.get("dry_run_mode_required") is True
        and lock_data.get("submission_execution_allowed") is False
        and lock_data.get("human_supervision_required") is True
    )
    results.append(
        _check(
            submission_lock_ok,
            "submission lock file contents",
            "submission lock file explicitly disables live submission paths",
            "submission lock file does not show locked production defaults",
            "Ensure the production lock template keeps final automation, live submission, and submission execution disabled.",
        )
    )

    production_submission_creds_embedded = any(
        env.get(key, "").strip()
        for key in (
            "LMCP_PRODUCTION_SUBMISSION_USERNAME",
            "LMCP_PRODUCTION_SUBMISSION_PASSWORD",
            "LMCP_PRODUCTION_PORTAL_USERNAME",
            "LMCP_PRODUCTION_PORTAL_PASSWORD",
        )
    )
    results.append(
        _check(
            not production_submission_creds_embedded,
            "production credentials are not embedded",
            "production submission credentials are not embedded in the package",
            "production submission credential values are embedded",
            "Keep production submission credential fields blank in the example package.",
        )
    )

    return results


def build_production_package_report(
    *,
    env_file: Path = ENV_FILE,
    compose_file: Path = COMPOSE_FILE,
    lock_file: Path = LOCK_FILE,
) -> Dict[str, Any]:
    env = _load_env_file(env_file)
    compose_text = compose_file.read_text(encoding="utf-8") if compose_file.exists() else ""
    lock_data = json.loads(lock_file.read_text(encoding="utf-8")) if lock_file.exists() else {}

    checks = _build_checks(env, compose_text, lock_data)
    pass_count = sum(1 for check in checks if check.level == "PASS")
    warn_count = sum(1 for check in checks if check.level == "WARN")
    fail_count = sum(1 for check in checks if check.level == "FAIL")

    overall_status = "FAIL" if fail_count else "WARN" if warn_count else "PASS"
    summary = {
        "overall_status": overall_status,
        "summary_counts": {"PASS": pass_count, "WARN": warn_count, "FAIL": fail_count},
        "checks": [check.__dict__ for check in checks],
        "env_file": str(env_file),
        "compose_file": str(compose_file),
        "lock_file": str(lock_file),
        "safety_model": {
            "final_automation_disabled": env.get("LMCP_ALLOW_FINAL_AUTOMATION") == "false",
            "dry_run_mode_enabled": env.get("LMCP_DRY_RUN_MODE") == "true",
            "human_supervision_required": env.get("LMCP_REQUIRE_HUMAN_SUPERVISION") == "true",
            "submission_lock_path": env.get("LMCP_SUBMISSION_LOCK_FILE", ""),
        },
        "production_governance_summary": {
            "runtime_separation": env.get("LMCP_RUNTIME_DIR", "").startswith("/app/runtime/production"),
            "observability_defined": _contains_all(compose_text, ("prometheus:", "grafana:")),
            "database_isolated": env.get("REDIS_URL") == "redis://redis:6379/0" and "@postgres:5432/" in env.get("DATABASE_URL", ""),
            "production_credentials_unset": not any(
                env.get(key, "").strip()
                for key in (
                    "LMCP_PRODUCTION_SUBMISSION_USERNAME",
                    "LMCP_PRODUCTION_SUBMISSION_PASSWORD",
                    "LMCP_PRODUCTION_PORTAL_USERNAME",
                    "LMCP_PRODUCTION_PORTAL_PASSWORD",
                )
            ),
        },
    }
    return summary


def _render_text(report: Dict[str, Any]) -> str:
    lines = [
        f"Production package validation: {report['overall_status']}",
        "Summary counts: PASS {PASS} WARN {WARN} FAIL {FAIL}".format(**report["summary_counts"]),
        f"Env file: {report['env_file']}",
        f"Compose file: {report['compose_file']}",
        f"Lock file: {report['lock_file']}",
        "",
        "Governance summary:",
        f"- runtime separated from staging: {'yes' if report['production_governance_summary']['runtime_separation'] else 'no'}",
        f"- observability services defined: {'yes' if report['production_governance_summary']['observability_defined'] else 'no'}",
        f"- database/broker isolated: {'yes' if report['production_governance_summary']['database_isolated'] else 'no'}",
        f"- production credentials unset: {'yes' if report['production_governance_summary']['production_credentials_unset'] else 'no'}",
        "",
        "Safety model:",
        f"- LMCP_ALLOW_FINAL_AUTOMATION=false: {'yes' if report['safety_model']['final_automation_disabled'] else 'no'}",
        f"- LMCP_DRY_RUN_MODE=true: {'yes' if report['safety_model']['dry_run_mode_enabled'] else 'no'}",
        f"- LMCP_REQUIRE_HUMAN_SUPERVISION=true: {'yes' if report['safety_model']['human_supervision_required'] else 'no'}",
        f"- submission lock file: {report['safety_model']['submission_lock_path']}",
        "",
    ]
    for check in report["checks"]:
        lines.append(f"{check['level']}: {check['name']} - {check['message']}")
        if check.get("remediation") and check["level"] != "PASS":
            lines.append(f"  remediation: {check['remediation']}")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the production deployment package governance example.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text")
    args = parser.parse_args(argv)

    report = build_production_package_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_render_text(report), end="")
    return 0 if report["overall_status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
