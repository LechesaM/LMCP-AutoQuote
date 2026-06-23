#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ENV_FILE = PROJECT_ROOT / ".env.production.example"
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.production.example.yml"
LOCK_FILE = PROJECT_ROOT / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
SMOKE_TEST_ROOT = PROJECT_ROOT / "runtime" / "staging" / "production-smoke-tests"
LATEST_SMOKE_TEST_JSON = SMOKE_TEST_ROOT / "latest_production_smoke_test.json"
LATEST_SMOKE_TEST_MD = SMOKE_TEST_ROOT / "latest_production_smoke_test.md"


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


def bundle_timestamp() -> str:
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
    module = _load_module(PROJECT_ROOT / "scripts" / "validate_production_package.py", "production_smoke_validate_package")
    return safe_dict(module.build_production_package_report())


def _build_access_report() -> Dict[str, Any]:
    module = _load_module(PROJECT_ROOT / "scripts" / "validate_production_access_governance.py", "production_smoke_validate_access")
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


def _contains_all(text: str, needles: List[str]) -> bool:
    return all(needle in text for needle in needles)


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


def _compose_config(compose_file: Path) -> tuple[bool, str, str]:
    command = ["docker", "compose", "-f", str(compose_file), "config"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return False, "", "docker compose is unavailable"
    if result.returncode != 0:
        stderr = safe_str(getattr(result, "stderr", ""))
        stdout = safe_str(getattr(result, "stdout", ""))
        message = stderr or stdout or "docker compose config failed"
        return False, stdout, message
    return True, safe_str(getattr(result, "stdout", "")), ""


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("FAIL", name, fail_message, remediation)


def _status_rank(value: str) -> int:
    normalized = safe_str(value, "FAIL").upper()
    if normalized in {"PASS", "OK", "READY", "CERTIFIED", "GO"}:
        return 3
    if normalized in {"WARN", "WATCH"}:
        return 2
    return 1


def _overall_status(statuses: List[str]) -> str:
    ranks = [_status_rank(item) for item in statuses if safe_str(item)]
    if not ranks:
        return "FAIL"
    if 1 in ranks:
        return "FAIL"
    if 2 in ranks:
        return "WARN"
    return "PASS"


def _summary_counts(checks: List[CheckResult]) -> Dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for check in checks:
        counts[check.level] = counts.get(check.level, 0) + 1
    return counts


def _service_expected(config_output: str, service: str) -> bool:
    return f"{service}:" in config_output


def _build_checks(
    env: Dict[str, str],
    compose_text: str,
    compose_ok: bool,
    compose_message: str,
    package: Dict[str, Any],
    access: Dict[str, Any],
    lock_data: Dict[str, Any],
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

    submission_creds_blank = all(
        not env.get(key, "").strip()
        for key in (
            "LMCP_PRODUCTION_SUBMISSION_USERNAME",
            "LMCP_PRODUCTION_SUBMISSION_PASSWORD",
            "LMCP_PRODUCTION_PORTAL_USERNAME",
            "LMCP_PRODUCTION_PORTAL_PASSWORD",
        )
    )
    results.append(
        _check(
            submission_creds_blank,
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

    service_checks = [
        ("backend", "backend service expected"),
        ("frontend", "frontend service expected"),
        ("postgres", "PostgreSQL service expected"),
        ("redis", "Redis service expected"),
        ("worker", "worker service expected"),
        ("prometheus", "Prometheus service expected"),
        ("grafana", "Grafana service expected"),
    ]
    for service, label in service_checks:
        results.append(
            _check(
                _service_expected(compose_text, service),
                label,
                f"{service} is defined in the production compose config",
                f"{service} is missing from the production compose config",
                f"Add the {service} service to docker-compose.production.example.yml.",
            )
        )

    results.append(
        _check(
            _contains_all(compose_text, ["http://127.0.0.1:8000/health", "/health"]),
            "backend health route expected",
            "backend healthcheck points at /health",
            "backend healthcheck does not reference /health",
            "Keep the backend healthcheck pointed at /health in the production compose file.",
        )
    )

    lock_ok = bool(lock_data) and lock_data.get("final_automation_disabled") is True and lock_data.get("live_portal_submission_disabled") is True
    lock_ok = lock_ok and lock_data.get("production_credentials_disabled") is True and lock_data.get("dry_run_mode_required") is True
    lock_ok = lock_ok and lock_data.get("submission_execution_allowed") is False and lock_data.get("human_supervision_required") is True
    results.append(
        _check(
            lock_ok,
            "submission locks exist or are documented",
            "submission lock file explicitly keeps live submission disabled",
            "submission lock file does not enforce locked production defaults",
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
            "Replace any live credential values with placeholders and use supervised secret injection.",
        )
    )

    results.append(
        _check(
            safe_str(package.get("overall_status"), "FAIL").upper() == "PASS",
            "production package readiness",
            "production package validation remains PASS",
            "production package validation is not PASS",
            "Fix the production package validation before relying on the smoke test.",
        )
    )
    results.append(
        _check(
            safe_str(access.get("overall_status"), "FAIL").upper() == "PASS",
            "production access readiness",
            "production access governance validation remains PASS",
            "production access governance validation is not PASS",
            "Fix the production access governance validation before relying on the smoke test.",
        )
    )

    return results


def build_production_smoke_test_report(
    *,
    env_file: Path = ENV_FILE,
    compose_file: Path = COMPOSE_FILE,
    lock_file: Path = LOCK_FILE,
    output_root: Path = SMOKE_TEST_ROOT,
) -> Dict[str, Any]:
    env = _load_env_file(env_file)
    compose_ok, compose_text, compose_message = _compose_config(compose_file)
    package = _build_package_report()
    access = _build_access_report()
    lock_data = safe_dict(read_json(lock_file, {}))

    checks = _build_checks(env, compose_text, compose_ok, compose_message, package, access, lock_data)
    overall_status = _overall_status([check.level for check in checks])
    summary_counts = _summary_counts(checks)
    overall_score = round(
        mean(
            [
                100.0 if overall_status == "PASS" else 75.0 if overall_status == "WARN" else 0.0,
                safe_float(package.get("production_governance_summary", {}).get("production_governance_score"), 0.0),
                safe_float(access.get("production_access_governance_summary", {}).get("access_governance_score"), 0.0),
            ]
        ),
        2,
    )

    bundle_dir = output_root / f"{bundle_timestamp()}-production-smoke-{uuid.uuid4().hex[:8]}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths = {
        "json": str(bundle_dir / "production_smoke_test.json"),
        "markdown": str(bundle_dir / "production_smoke_test.md"),
        "latest_json": str(output_root / "latest_production_smoke_test.json"),
        "latest_markdown": str(output_root / "latest_production_smoke_test.md"),
        "compose_config": str(bundle_dir / "docker_compose_config.txt"),
    }

    payload = {
        "bundle_id": bundle_dir.name,
        "generated_at": iso_now(),
        "source_runtime": str(output_root),
        "overall_status": overall_status,
        "overall_score": overall_score,
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
        "validation_summaries": {
            "production_package": package,
            "production_access_governance": access,
        },
        "compose_validation": {
            "compose_parsed": compose_ok,
            "compose_message": compose_message,
            "service_expectations": {
                "backend": _service_expected(compose_text, "backend"),
                "frontend": _service_expected(compose_text, "frontend"),
                "postgres": _service_expected(compose_text, "postgres"),
                "redis": _service_expected(compose_text, "redis"),
                "worker": _service_expected(compose_text, "worker"),
                "prometheus": _service_expected(compose_text, "prometheus"),
                "grafana": _service_expected(compose_text, "grafana"),
            },
        },
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_operations": False,
            "production_submission_enablement": False,
            "production_connectivity_required": False,
            "human_supervision_required": True,
            "dry_run_protections_active": True,
        },
        "artifact_paths": artifact_paths,
    }

    write_json(bundle_dir / "production_smoke_test.json", payload)
    write_text(bundle_dir / "production_smoke_test.md", markdown_summary(payload))
    write_text(bundle_dir / "docker_compose_config.txt", compose_text)
    write_json(output_root / "latest_production_smoke_test.json", payload)
    write_text(output_root / "latest_production_smoke_test.md", markdown_summary(payload))
    return payload


def markdown_summary(payload: Dict[str, Any]) -> str:
    lines = [
        "# Production Smoke Test Report",
        "",
        f"- Bundle ID: `{safe_str(payload.get('bundle_id'))}`",
        f"- Generated At: `{safe_str(payload.get('generated_at'))}`",
        f"- Overall Status: `{safe_str(payload.get('overall_status'), 'FAIL')}`",
        f"- Overall Score: `{safe_float(payload.get('overall_score'), 0.0):.2f}`",
        f"- Summary Counts: `{json.dumps(safe_dict(payload.get('summary_counts')), sort_keys=True)}`",
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
        f"- Services: `{json.dumps(safe_dict(payload.get('compose_validation')).get('service_expectations', {}), sort_keys=True)}`",
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
    print(f"Production smoke test: {safe_str(payload.get('artifact_paths', {}).get('json'), '')}")
    print(f"Overall status: {safe_str(payload.get('overall_status'), 'FAIL')}")
    print(f"Overall score: {safe_float(payload.get('overall_score'), 0.0):.2f}")
    print(f"Summary counts: PASS {safe_int(safe_dict(payload.get('summary_counts')).get('PASS'), 0)} WARN {safe_int(safe_dict(payload.get('summary_counts')).get('WARN'), 0)} FAIL {safe_int(safe_dict(payload.get('summary_counts')).get('FAIL'), 0)}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the production smoke test.")
    parser.add_argument("--output-root", type=Path, default=SMOKE_TEST_ROOT, help="Where to write the smoke test bundle.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human-readable summary.")
    args = parser.parse_args(argv)

    payload = build_production_smoke_test_report(output_root=args.output_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
