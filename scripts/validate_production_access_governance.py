#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


sys.dont_write_bytecode = True

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env.production.example"
COMPOSE_FILE = ROOT_DIR / "docker-compose.production.example.yml"
LOCK_FILE = ROOT_DIR / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
ACCESS_README = ROOT_DIR / "runtime" / "production" / "access_governance" / "README.md"

PLACEHOLDER_KEYS = (
    "LMCP_SECRET_KEY",
    "POSTGRES_PASSWORD",
    "LMCP_GRAFANA_ADMIN_PASSWORD",
    "LMCP_PRODUCTION_SUBMISSION_USERNAME",
    "LMCP_PRODUCTION_SUBMISSION_PASSWORD",
    "LMCP_PRODUCTION_PORTAL_USERNAME",
    "LMCP_PRODUCTION_PORTAL_PASSWORD",
)

REQUIRED_RBAC_ROLES = {
    "operator",
    "supervisor",
    "security_admin",
    "release_manager",
    "executive_override",
    "production_observer",
}


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


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("FAIL", name, fail_message, remediation)


def _contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _load_lock_data(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_checks(env: Dict[str, str], compose_text: str, lock_data: Dict[str, Any], access_readme_text: str) -> List[CheckResult]:
    results: List[CheckResult] = []

    results.append(
        _check(
            ENV_FILE.exists(),
            "production env example exists",
            f"{ENV_FILE.name} is present",
            f"{ENV_FILE.name} is missing",
            "Add the production example environment file before validating access governance.",
        )
    )
    results.append(
        _check(
            COMPOSE_FILE.exists(),
            "production compose file exists",
            f"{COMPOSE_FILE.name} is present",
            f"{COMPOSE_FILE.name} is missing",
            "Add the production compose example before validating access governance.",
        )
    )
    results.append(
        _check(
            ACCESS_README.exists(),
            "access governance placeholder exists",
            "production access-governance README is present",
            "production access-governance README is missing",
            "Create runtime/production/access_governance/README.md as a placeholder structure only.",
        )
    )

    secret_checks = []
    for key in PLACEHOLDER_KEYS:
        value = env.get(key, "")
        secret_checks.append(_looks_placeholder(value))
    results.append(
        _check(
            all(secret_checks),
            "production credentials are placeholders only",
            "credential-bearing values are blank or placeholder text",
            "one or more credential-bearing values are not placeholder-only",
            "Keep production credentials blank or set them to explicit placeholder values in the example package.",
        )
    )

    sensitive_text = "\n".join([_text(ENV_FILE), _text(COMPOSE_FILE), access_readme_text])
    secret_markers = (
        "BEGIN PRIVATE KEY",
        "-----BEGIN",
        "AKIA",
        "ghp_",
        "xoxb-",
        "sk-",
        "oauth_token=",
        "auth_token=",
        "real-password",
        "real-secret",
        "supersecret",
    )
    results.append(
        _check(
            not any(marker in sensitive_text for marker in secret_markers),
            "no embedded secrets",
            "no obvious embedded secret material was found in the production package",
            "suspicious secret-like material was found in the production package",
            "Replace any embedded secret material with placeholders and inject real values via a supervised secret manager.",
        )
    )

    rbac_roles = set(_split_csv(env.get("LMCP_RBAC_ROLES", "")))
    results.append(
        _check(
            REQUIRED_RBAC_ROLES.issubset(rbac_roles),
            "RBAC roles are defined",
            "production RBAC roles include operator, supervision, executive, and observer roles",
            "required RBAC roles are missing from the production package",
            "Define the production RBAC roles in .env.production.example and the compose environment.",
        )
    )

    supervision_roles = set(_split_csv(env.get("LMCP_SUPERVISION_ROLES", "")))
    results.append(
        _check(
            supervision_roles == {"operator", "supervisor"},
            "supervision roles are isolated",
            "supervision roles are limited to operator and supervisor",
            "supervision roles are not isolated to operator and supervisor",
            "Keep supervision roles separate from executive override or deployment roles.",
        )
    )

    executive_override_roles = set(_split_csv(env.get("LMCP_EXECUTIVE_OVERRIDE_ROLES", "")))
    results.append(
        _check(
            executive_override_roles == {"executive_override"},
            "executive override roles are isolated",
            "executive override is isolated to a dedicated role",
            "executive override roles are not isolated",
            "Keep executive override limited to the dedicated executive_override role.",
        )
    )

    deployment_access = env.get("LMCP_DEPLOYMENT_ACCESS_SEGREGATION") == "true"
    observability_access = env.get("LMCP_OBSERVABILITY_ACCESS_SEGREGATION") == "true"
    results.append(
        _check(
            deployment_access,
            "deployment access segregation exists",
            "deployment access segregation is enabled",
            "deployment access segregation is not enabled",
            "Set LMCP_DEPLOYMENT_ACCESS_SEGREGATION=true in the production package.",
        )
    )
    results.append(
        _check(
            observability_access,
            "observability access segregation exists",
            "observability access segregation is enabled",
            "observability access segregation is not enabled",
            "Set LMCP_OBSERVABILITY_ACCESS_SEGREGATION=true in the production package.",
        )
    )

    admin_escalation_roles = set(_split_csv(env.get("LMCP_ADMIN_ESCALATION_ROLES", "")))
    results.append(
        _check(
            {"security_admin", "release_manager"}.issubset(admin_escalation_roles),
            "admin escalation paths exist",
            "admin escalation roles include security_admin and release_manager",
            "admin escalation roles are incomplete",
            "Define the production escalation path through security_admin and release_manager.",
        )
    )

    production_lock_path = env.get("LMCP_SUBMISSION_LOCK_FILE", "")
    lock_expected = "/app/runtime/production/go_live_guards/submission_locks.json"
    lock_ok = production_lock_path == lock_expected and lock_data.get("submission_execution_allowed") is False
    lock_ok = lock_ok and lock_data.get("final_automation_disabled") is True and lock_data.get("live_portal_submission_disabled") is True
    lock_ok = lock_ok and lock_data.get("production_credentials_disabled") is True and lock_data.get("dry_run_mode_required") is True
    lock_ok = lock_ok and lock_data.get("human_supervision_required") is True
    results.append(
        _check(
            lock_ok,
            "production lock enforcement exists",
            "production submission lock file enforces supervised lock-only execution",
            "production submission lock enforcement is incomplete",
            "Keep the production submission lock file locked with live submission disabled.",
        )
    )

    audit_retention_days = _safe_int(env.get("LMCP_AUDIT_RETENTION_DAYS", "0") or "0")
    results.append(
        _check(
            env.get("LMCP_AUDIT_RETENTION_ENFORCED") == "true" and audit_retention_days >= 3650,
            "audit retention enforcement exists",
            "audit retention is enabled and set to a long-term production retention period",
            "audit retention enforcement is not sufficiently strict",
            "Keep audit retention enforcement enabled and retain production audit history for at least 3650 days.",
        )
    )

    results.append(
        _check(
            _contains_all(
                compose_text,
                (
                    "LMCP_ACCESS_GOVERNANCE_PROFILE: locked_production",
                    "LMCP_RBAC_ROLES: operator,supervisor,security_admin,release_manager,executive_override,production_observer",
                    'LMCP_DEPLOYMENT_ACCESS_SEGREGATION: "true"',
                    'LMCP_OBSERVABILITY_ACCESS_SEGREGATION: "true"',
                    "LMCP_ADMIN_ESCALATION_ROLES: security_admin,release_manager",
                    'LMCP_PRODUCTION_LOCK_ENFORCED: "true"',
                    'LMCP_AUDIT_RETENTION_ENFORCED: "true"',
                ),
            ),
            "compose access controls are declared",
            "compose template declares the production access control surface",
            "compose template is missing one or more access control declarations",
            "Keep the access governance declarations mirrored in docker-compose.production.example.yml.",
        )
    )

    results.append(
        _check(
            access_readme_text.strip() != "" and "No real credentials" in access_readme_text and "Human supervision remains mandatory" in access_readme_text,
            "access governance placeholder structure",
            "access governance README documents the placeholder-only structure",
            "access governance README does not document the placeholder structure",
            "Keep runtime/production/access_governance/README.md as a structure-only placeholder with no secrets.",
        )
    )

    return results


def build_production_access_governance_report(
    *,
    env_file: Path = ENV_FILE,
    compose_file: Path = COMPOSE_FILE,
    lock_file: Path = LOCK_FILE,
    access_readme: Path = ACCESS_README,
) -> Dict[str, Any]:
    env = _load_env_file(env_file)
    compose_text = compose_file.read_text(encoding="utf-8") if compose_file.exists() else ""
    lock_data = _load_lock_data(lock_file)
    access_readme_text = access_readme.read_text(encoding="utf-8") if access_readme.exists() else ""

    checks = _build_checks(env, compose_text, lock_data, access_readme_text)
    pass_count = sum(1 for check in checks if check.level == "PASS")
    warn_count = sum(1 for check in checks if check.level == "WARN")
    fail_count = sum(1 for check in checks if check.level == "FAIL")
    overall_status = "FAIL" if fail_count else "WARN" if warn_count else "PASS"

    report = {
        "overall_status": overall_status,
        "summary_counts": {"PASS": pass_count, "WARN": warn_count, "FAIL": fail_count},
        "checks": [check.__dict__ for check in checks],
        "env_file": str(env_file),
        "compose_file": str(compose_file),
        "lock_file": str(lock_file),
        "access_governance_readme": str(access_readme),
        "production_access_governance_summary": {
            "credentials_placeholder_only": all(_looks_placeholder(env.get(key, "")) for key in PLACEHOLDER_KEYS),
            "rbac_roles_defined": REQUIRED_RBAC_ROLES.issubset(set(_split_csv(env.get("LMCP_RBAC_ROLES", "")))),
            "supervision_roles_isolated": set(_split_csv(env.get("LMCP_SUPERVISION_ROLES", ""))) == {"operator", "supervisor"},
            "executive_override_roles_isolated": set(_split_csv(env.get("LMCP_EXECUTIVE_OVERRIDE_ROLES", ""))) == {"executive_override"},
            "deployment_access_segregation": env.get("LMCP_DEPLOYMENT_ACCESS_SEGREGATION") == "true",
            "observability_access_segregation": env.get("LMCP_OBSERVABILITY_ACCESS_SEGREGATION") == "true",
            "admin_escalation_paths": {"security_admin", "release_manager"}.issubset(set(_split_csv(env.get("LMCP_ADMIN_ESCALATION_ROLES", "")))),
            "production_lock_enforced": lock_data.get("submission_execution_allowed") is False and lock_data.get("human_supervision_required") is True,
            "audit_retention_enforced": env.get("LMCP_AUDIT_RETENTION_ENFORCED") == "true",
        },
        "safety_model": {
            "final_automation_disabled": env.get("LMCP_ALLOW_FINAL_AUTOMATION") == "false",
            "dry_run_mode_enabled": env.get("LMCP_DRY_RUN_MODE") == "true",
            "human_supervision_required": env.get("LMCP_REQUIRE_HUMAN_SUPERVISION") == "true",
            "submission_lock_path": env.get("LMCP_SUBMISSION_LOCK_FILE", ""),
        },
    }
    return report


def _render_text(report: Dict[str, Any]) -> str:
    lines = [
        f"Production access governance validation: {report['overall_status']}",
        "Summary counts: PASS {PASS} WARN {WARN} FAIL {FAIL}".format(**report["summary_counts"]),
        f"Env file: {report['env_file']}",
        f"Compose file: {report['compose_file']}",
        f"Lock file: {report['lock_file']}",
        f"Access governance README: {report['access_governance_readme']}",
        "",
        "Access governance summary:",
        f"- credentials placeholder only: {'yes' if report['production_access_governance_summary']['credentials_placeholder_only'] else 'no'}",
        f"- RBAC roles defined: {'yes' if report['production_access_governance_summary']['rbac_roles_defined'] else 'no'}",
        f"- supervision roles isolated: {'yes' if report['production_access_governance_summary']['supervision_roles_isolated'] else 'no'}",
        f"- executive override roles isolated: {'yes' if report['production_access_governance_summary']['executive_override_roles_isolated'] else 'no'}",
        f"- deployment access segregation: {'yes' if report['production_access_governance_summary']['deployment_access_segregation'] else 'no'}",
        f"- observability access segregation: {'yes' if report['production_access_governance_summary']['observability_access_segregation'] else 'no'}",
        f"- admin escalation paths: {'yes' if report['production_access_governance_summary']['admin_escalation_paths'] else 'no'}",
        f"- production lock enforced: {'yes' if report['production_access_governance_summary']['production_lock_enforced'] else 'no'}",
        f"- audit retention enforced: {'yes' if report['production_access_governance_summary']['audit_retention_enforced'] else 'no'}",
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
    parser = argparse.ArgumentParser(description="Validate production secrets and access governance.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text")
    args = parser.parse_args(argv)

    report = build_production_access_governance_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_render_text(report), end="")
    return 0 if report["overall_status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
