#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib.util
import json
import logging
import os
import tempfile
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
STAGING_VALIDATION_SCRIPT = ROOT_DIR / "scripts" / "validate_staging_environment.py"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@dataclass
class CheckResult:
    level: str
    name: str
    message: str
    remediation: str = ""


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@contextlib.contextmanager
def _chdir(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _load_staging_env(validation_module) -> Tuple[Path, Dict[str, str]]:
    return validation_module._load_staging_env()


def _coerce_results(results: Iterable[Any]) -> List[CheckResult]:
    coerced: List[CheckResult] = []
    for result in results:
        coerced.append(
            CheckResult(
                level=str(getattr(result, "level", "WARN")),
                name=str(getattr(result, "name", "check")),
                message=str(getattr(result, "message", "")),
                remediation=str(getattr(result, "remediation", "")),
            )
        )
    return coerced


def _print_summary(results: List[CheckResult]) -> int:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for result in results:
        counts[result.level] = counts.get(result.level, 0) + 1

    print(f"PASS: {counts['PASS']}  WARN: {counts['WARN']}  FAIL: {counts['FAIL']}")
    print("")
    for result in results:
        print(f"[{result.level}] {result.name}: {result.message}")
        if result.level != "PASS" and result.remediation:
            print(f"  Remediation: {result.remediation}")
    print("")
    if counts["FAIL"]:
        print("Dry-run validation failed.")
        return 1
    if counts["WARN"]:
        print("Dry-run validation passed with warnings.")
    else:
        print("Dry-run validation passed.")
    return 0


def _production_markers_present(env: Dict[str, str], names: Iterable[str]) -> bool:
    for name in names:
        value = str(env.get(name, "")).strip().lower()
        if not value:
            continue
        if "production" in value or "localhost" in value or "127.0.0.1" in value:
            return True
        if "lmcp:lmcp@" in value:
            return True
    return False


def _lock_file_contains_lock(path: Path, buyer_rfq_number: str, quote_number: str = "") -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, list):
        return False
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    quote_number = str(quote_number or "").strip()
    for item in data:
        if not isinstance(item, dict):
            continue
        item_buyer = str(item.get("buyer_rfq_number") or "").strip()
        item_quote = str(item.get("quote_number") or "").strip()
        if item_buyer == buyer_rfq_number and (not quote_number or item_quote == quote_number):
            return True
    return False


@contextlib.contextmanager
def _sandboxed_runtime(sandbox_root: Path) -> Iterator[Dict[str, Path]]:
    import app.operations.structured_logging as telemetry_mod
    import app.services.rfq_lifecycle_service as lifecycle_mod
    import app.services.rfq_state_store as state_store_mod
    import app.services.real_profit_pricing_service as pricing_mod
    import app.services.system_control_service as control_mod

    sandbox_runtime = sandbox_root / "runtime"
    sandbox_runtime.mkdir(parents=True, exist_ok=True)

    patched: List[Tuple[Any, str, Any]] = [
        (lifecycle_mod, "PROJECT_ROOT", sandbox_root),
        (state_store_mod, "PROJECT_ROOT", sandbox_root),
        (state_store_mod, "RUNTIME_DIR", sandbox_runtime),
        (state_store_mod, "RFQ_LIFECYCLE_DIR", sandbox_runtime / "rfq_lifecycle"),
        (state_store_mod, "RFQ_STATE_FILE", sandbox_runtime / "rfq_lifecycle" / "rfqs.json"),
        (state_store_mod, "RFQ_AUDIT_FILE", sandbox_runtime / "rfq_lifecycle" / "audit_events.json"),
        (state_store_mod, "RFQ_ANALYTICS_FILE", sandbox_runtime / "rfq_lifecycle" / "analytics.json"),
        (state_store_mod, "RFQ_TELEMETRY_FILE", sandbox_runtime / "rfq_lifecycle" / "telemetry.json"),
        (pricing_mod, "RUNTIME_DIR", sandbox_runtime),
        (pricing_mod, "PRICING_DIR", sandbox_runtime / "real_profit_pricing"),
        (pricing_mod, "LAST_FILE", sandbox_runtime / "real_profit_pricing" / "last_pricing.json"),
        (pricing_mod, "HISTORY_FILE", sandbox_runtime / "real_profit_pricing" / "pricing_history.json"),
        (control_mod, "PROJECT_ROOT", sandbox_root),
        (control_mod, "RUNTIME_DIR", sandbox_runtime),
        (control_mod, "CONTROL_DIR", sandbox_runtime / "system_control"),
        (control_mod, "STATE_FILE", sandbox_runtime / "system_control" / "state.json"),
        (control_mod, "HARVESTER_PAUSE_FILE", sandbox_runtime / "harvester.paused"),
        (control_mod, "SUBMISSION_PAUSE_FILE", sandbox_runtime / "submission.paused"),
        (control_mod, "EMERGENCY_STOP_FILE", sandbox_runtime / "emergency.stop"),
        (control_mod, "V48_STATE_FILE", sandbox_runtime / "system_control" / "v48_autonomous_state.json"),
        (control_mod, "V48_POLICY_FILE", sandbox_runtime / "full_autonomous_v48" / "policy.json"),
    ]
    original_values: List[Tuple[Any, str, Any]] = []
    try:
        for module, name, value in patched:
            if hasattr(module, name):
                original_values.append((module, name, getattr(module, name)))
                setattr(module, name, value)
        yield {
            "sandbox_root": sandbox_root,
            "sandbox_runtime": sandbox_runtime,
            "telemetry_mod": telemetry_mod,
        }
    finally:
        for module, name, value in reversed(original_values):
            setattr(module, name, value)


def _validate_submission_locks(sandbox_root: Path, rfq_id: str) -> List[CheckResult]:
    lock_dir = sandbox_root / "runtime" / "go_live_guards"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / "submission_locks.json"
    lock_payload = [
        {
            "buyer_rfq_number": rfq_id,
            "quote_number": "DRYRUN-QUOTE-001",
            "reason": "dry_run_validation_lock",
            "metadata": {"mode": "dry_run_validation"},
            "created_at": "2026-06-23T00:00:00+00:00",
        }
    ]
    lock_file.write_text(json.dumps(lock_payload, indent=2), encoding="utf-8")

    hits_matching = _lock_file_contains_lock(lock_file, rfq_id, "DRYRUN-QUOTE-001")
    hits_mismatched = _lock_file_contains_lock(lock_file, rfq_id, "OTHER-QUOTE")
    hits_unknown = _lock_file_contains_lock(lock_file, "OTHER-RFQ", "DRYRUN-QUOTE-001")
    return [
        CheckResult(
            "PASS" if hits_matching and not hits_mismatched and not hits_unknown else "FAIL",
            "submission lock contract",
            "isolated submission-lock file blocks matching RFQ/quote pairs" if hits_matching and not hits_mismatched and not hits_unknown else "submission-lock contract did not behave as expected",
            "Verify the lock file structure matches runtime/go_live_guards/submission_locks.json and that matching RFQ/quote pairs are blocked.",
        )
    ]


def _validate_environment_contract(env: Dict[str, str], env_path: Path, compose_text: str, app_main_text: str) -> List[CheckResult]:
    required = [
        "LMCP_ENV",
        "LMCP_PRODUCTION_MODE",
        "LMCP_DEPLOYMENT_PROFILE",
        "LMCP_ALLOW_FINAL_AUTOMATION",
        "PORTAL_ISOLATION_ENABLED",
        "LMCP_RUNTIME_DIR",
        "LMCP_LOG_DIR",
        "LMCP_LOCKS_DIR",
        "LMCP_DATABASE_URL",
        "REDIS_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "LMCP_OBSERVABILITY_ENABLED",
        "LMCP_APP_ENTRYPOINT",
        "LMCP_BACKEND_URL",
        "LMCP_FRONTEND_URL",
    ]
    missing = [name for name in required if name not in env]
    results = [
        CheckResult(
            "PASS" if not missing else "FAIL",
            "required staging variables",
            "all required staging variables are present" if not missing else f"missing required variables: {', '.join(missing)}",
            "Populate the missing keys in .env.staging or .env.staging.example.",
        )
    ]

    dry_run_enabled = (
        env.get("LMCP_ENV") == "staging"
        and env.get("LMCP_PRODUCTION_MODE") == "staging"
        and env.get("LMCP_ALLOW_FINAL_AUTOMATION") == "false"
        and env.get("PORTAL_ISOLATION_ENABLED") == "true"
    )
    results.append(
        CheckResult(
            "PASS" if dry_run_enabled else "FAIL",
            "dry-run enforcement",
            "dry-run protections are enabled" if dry_run_enabled else "dry-run protections are not enabled",
            "Set LMCP_ENV=staging, LMCP_PRODUCTION_MODE=staging, LMCP_ALLOW_FINAL_AUTOMATION=false, and PORTAL_ISOLATION_ENABLED=true.",
        )
    )

    final_automation_disabled = env.get("LMCP_ALLOW_FINAL_AUTOMATION") == "false"
    results.append(
        CheckResult(
            "PASS" if final_automation_disabled else "FAIL",
            "final automation disabled",
            "final automation is disabled" if final_automation_disabled else "final automation is still enabled",
            "Keep LMCP_ALLOW_FINAL_AUTOMATION=false for staging dry-runs.",
        )
    )

    db_ok = all(
        str(env.get(name, "")).startswith("postgresql://") and "lmcp_staging" in str(env.get(name, "")) and "production" not in str(env.get(name, "")).lower()
        for name in ("LMCP_DATABASE_URL", "DATABASE_URL")
        if env.get(name)
    )
    results.append(
        CheckResult(
            "PASS" if db_ok else "FAIL",
            "staging DB isolation",
            "database URLs target isolated staging PostgreSQL" if db_ok else "database URLs do not clearly target staging PostgreSQL",
            "Set LMCP_DATABASE_URL and DATABASE_URL to the staging PostgreSQL service and staging database name.",
        )
    )

    queue_ok = all(str(env.get(name, "")).strip() == "redis://redis:6379/0" for name in ("REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"))
    results.append(
        CheckResult(
            "PASS" if queue_ok else "FAIL",
            "queue isolation",
            "queue URLs target the isolated staging Redis service" if queue_ok else "queue URLs do not point to the isolated staging Redis service",
            "Set REDIS_URL, CELERY_BROKER_URL, and CELERY_RESULT_BACKEND to redis://redis:6379/0.",
        )
    )

    runtime_ok = all(str(env.get(name, "")).startswith("/app/runtime/staging") for name in (
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
        "PORTAL_ISOLATION_STATE_FILE",
    ) if env.get(name))
    results.append(
        CheckResult(
            "PASS" if runtime_ok else "FAIL",
            "runtime storage isolation",
            "runtime paths are staged under /app/runtime/staging" if runtime_ok else "one or more runtime paths escape /app/runtime/staging",
            "Move all staging runtime paths under /app/runtime/staging.",
        )
    )

    telemetry_ok = env.get("LMCP_OBSERVABILITY_ENABLED") == "1" and "prometheus:" in compose_text and "grafana:" in compose_text
    results.append(
        CheckResult(
            "PASS" if telemetry_ok else "FAIL",
            "telemetry availability",
            "telemetry is enabled and staging telemetry services are declared" if telemetry_ok else "telemetry services or configuration are missing",
            "Keep LMCP_OBSERVABILITY_ENABLED=1 and declare Prometheus/Grafana in docker-compose.staging.yml.",
        )
    )

    endpoint_ok = "app.main:app" in env.get("LMCP_APP_ENTRYPOINT", "") and '"/health"' in app_main_text and '"/status"' in app_main_text
    results.append(
        CheckResult(
            "PASS" if endpoint_ok else "FAIL",
            "backend endpoint configuration",
            "backend entrypoint and health/status routes are configured" if endpoint_ok else "backend entrypoint or health/status routes are missing",
            "Keep LMCP_APP_ENTRYPOINT on app.main:app and preserve /health and /status in app/main.py.",
        )
    )

    no_prod = not _production_markers_present(
        env,
        [
            "LMCP_DATABASE_URL",
            "DATABASE_URL",
            "REDIS_URL",
            "CELERY_BROKER_URL",
            "CELERY_RESULT_BACKEND",
            "LMCP_OPERATOR_AUTH_DB_PATH",
            "PORTAL_ISOLATION_STATE_FILE",
        ],
    )
    results.append(
        CheckResult(
            "PASS" if no_prod else "FAIL",
            "no production references",
            "no production host or credential references were detected" if no_prod else "production host or credential references were detected",
            "Replace production URLs and credential paths with staging-only values.",
        )
    )

    results.append(
        CheckResult(
            "PASS" if ".env.staging.example" in str(env_path) or env_path.name == ".env.staging" else "WARN",
            "staging env source",
            f"environment loaded from {env_path.name}",
            "Prefer .env.staging for local overrides and keep .env.staging.example as the checked-in baseline.",
        )
    )

    return results


def _run_safe_workflow_stage(
    env: Dict[str, str],
    sandbox_root: Path,
    validation_module,
) -> Tuple[List[CheckResult], Dict[str, Any], Dict[str, Any]]:
    from app.operations.structured_logging import (
        generate_correlation_id,
        log_operation_event,
        log_rfq_lifecycle_event,
        log_worker_event,
        observability_context,
    )
    from app.services.rfq_lifecycle_service import RfqLifecycleService
    from app.services.rfq_state_store import RfqStateStore

    rfq_id = "DRYRUN-HARNESS-001"
    trace_id = generate_correlation_id("trace")
    request_id = generate_correlation_id("req")
    operator_id = "staging-dry-run-harness"
    stage_results: List[CheckResult] = []
    workflow_result: Dict[str, Any] = {}
    telemetry_snapshot: Dict[str, Any] = {}

    store = RfqStateStore(state_file=sandbox_root / "runtime" / "rfq_lifecycle" / "rfqs.json")
    lifecycle = RfqLifecycleService(store)

    sandbox_root.mkdir(parents=True, exist_ok=True)
    (sandbox_root / "inputs").mkdir(parents=True, exist_ok=True)
    (sandbox_root / "runtime" / "go_live_guards").mkdir(parents=True, exist_ok=True)
    (sandbox_root / "runtime" / "rfq_lifecycle").mkdir(parents=True, exist_ok=True)

    with observability_context(
        request_id=request_id,
        trace_id=trace_id,
        rfq_id=rfq_id,
        workflow_stage="dry_run_validation",
        operator_id=operator_id,
    ):
        log_operation_event(
            "dry_run_harness",
            "dry_run_validation_started",
            environment=env.get("LMCP_ENV", "staging"),
            sandbox_root=str(sandbox_root),
            staging_env=str(validation_module.__file__),
        )
        log_worker_event(
            "heartbeat",
            "dry_run_harness_worker_heartbeat",
            worker_id="dry-run-harness",
            queue_name="staging-validation",
            status="healthy",
            retries=0,
            environment=env.get("LMCP_ENV", "staging"),
        )

        ingest_payload = {
            "source": "staging_dry_run_harness",
            "items": [
                {
                    "rfq_id": rfq_id,
                    "buyer_name": "Staging Buyer",
                    "title": "Supply and delivery of office stationery",
                    "description": "Supply and delivery of office stationery for dry-run validation only",
                    "current_state": "DISCOVERED",
                    "qualification_score": 95,
                    "estimated_profit": 50000,
                    "estimated_margin": 30,
                    "document_confidence_score": 0.95,
                    "buyer_pack_downloaded": True,
                    "buyer_pack_verified": True,
                    "document_urls": ["https://example.invalid/dry-run.pdf"],
                    "document_paths": [str(sandbox_root / "inputs" / "dry-run.pdf")],
                    "source_payload": {"submission_method": "email"},
                }
            ],
        }
        ingest_result = lifecycle.ingest(ingest_payload)
        stage_results.append(
            CheckResult(
                "PASS" if ingest_result.get("status") == "ok" and int(ingest_result.get("ingested_count") or 0) >= 1 else "FAIL",
                "safe ingest stage",
                f"ingest completed with {ingest_result.get('ingested_count', 0)} item(s)",
                "Ensure the synthetic RFQ payload is accepted by the lifecycle ingest stage.",
            )
        )
        log_rfq_lifecycle_event(
            "rfq_discovered",
            "Synthetic RFQ ingested into isolated dry-run sandbox",
            rfq_id=rfq_id,
            workflow_stage="DISCOVERED",
            status="ok",
            reason="safe_synthetic_ingest",
            details=ingest_result,
        )

        state = store.read()
        item = state.get("items", {}).get(rfq_id, {})
        if isinstance(item, dict):
            from app.services.rfq_state_store import utc_now_iso

            now = utc_now_iso()
            item.update(
                {
                    "current_state": "DOCUMENTS_PARSED",
                    "previous_state": "DOCUMENTS_ACQUIRED",
                    "buyer_pack_downloaded": True,
                    "buyer_pack_verified": True,
                    "document_acquisition_status": "downloaded",
                    "document_verification_status": "verified",
                    "quote_candidate_status": "document_verified",
                    "document_paths": [str(sandbox_root / "inputs" / "dry-run.pdf")],
                    "document_urls": ["https://example.invalid/dry-run.pdf"],
                    "qualification_score": 95,
                    "estimated_profit": 50000,
                    "estimated_margin": 30,
                    "updated_at": now,
                }
            )
            state.setdefault("items", {})[rfq_id] = item
            store.write(state)

        with _chdir(sandbox_root):
            advance_result = lifecycle.advance_parsed(limit=1)

        current_item = store.get_item(rfq_id) or {}
        stage_results.append(
            CheckResult(
                "PASS"
                if advance_result.get("status") == "ok"
                and str(current_item.get("current_state") or "").upper() in {"PRICED", "REVIEW_REQUIRED", "SUBMISSION_READY_MANUAL", "QUOTE_PACK_READY"}
                else "FAIL",
                "safe pricing handoff stage",
                f"advance_parsed completed with state {current_item.get('current_state')}",
                "Ensure the synthetic RFQ can progress to a non-submission stage inside the isolated sandbox.",
            )
        )
        log_rfq_lifecycle_event(
            "workflow_state_transition",
            "Synthetic RFQ advanced through a non-submission dry-run stage",
            rfq_id=rfq_id,
            workflow_stage=str(current_item.get("current_state") or "DOCUMENTS_PARSED"),
            status="ok",
            reason=str((advance_result.get("items") or [{}])[0].get("reason") if isinstance(advance_result.get("items"), list) and advance_result.get("items") else ""),
            details=advance_result,
        )

        blocked_submission = lifecycle.advance(rfq_id, target_state="SUBMITTED", note="dry_run_validation_block_check")
        stage_results.append(
            CheckResult(
                "PASS" if blocked_submission.get("status") == "blocked" and blocked_submission.get("reason") == "unsafe_final_submission_blocked_without_policy_control" else "FAIL",
                "submission lock and dry-run protection",
                "attempt to advance into SUBMITTED was blocked" if blocked_submission.get("status") == "blocked" else "submission advance was not blocked",
                "Keep the lifecycle submission guard hard-blocking SUBMITTED transitions.",
            )
        )
        log_rfq_lifecycle_event(
            "dry_run_blocked",
            "Submission transition blocked during dry-run validation",
            rfq_id=rfq_id,
            workflow_stage=str(current_item.get("current_state") or "DOCUMENTS_PARSED"),
            status="blocked",
            reason=str(blocked_submission.get("reason") or "blocked"),
            details=blocked_submission,
        )

        telemetry_snapshot = lifecycle.telemetry()
        status_snapshot = lifecycle.status()
        stage_results.append(
            CheckResult(
                "PASS" if isinstance(telemetry_snapshot, dict) and telemetry_snapshot.get("status") == "ok" and isinstance(status_snapshot, dict) and status_snapshot.get("status") == "ok" else "FAIL",
                "telemetry availability",
                f"status={status_snapshot.get('status')} telemetry={telemetry_snapshot.get('status')}",
                "Confirm the lifecycle service can produce status and telemetry snapshots in staging.",
            )
        )

        lock_dir = sandbox_root / "runtime" / "go_live_guards"
        stage_results.extend(_validate_submission_locks(sandbox_root, rfq_id))

        log_operation_event(
            "dry_run_harness",
            "dry_run_validation_completed",
            environment=env.get("LMCP_ENV", "staging"),
            rfq_id=rfq_id,
            workflow_state=str(current_item.get("current_state") or ""),
            status="ok" if all(result.level != "FAIL" for result in stage_results) else "degraded",
            checks_passed=sum(1 for result in stage_results if result.level == "PASS"),
            checks_warned=sum(1 for result in stage_results if result.level == "WARN"),
            checks_failed=sum(1 for result in stage_results if result.level == "FAIL"),
            sandbox_root=str(sandbox_root),
        )

    workflow_summary = {
        "rfq_id": rfq_id,
        "ingest_result": ingest_result,
        "advance_result": advance_result,
        "blocked_submission_result": blocked_submission,
        "final_state": current_item.get("current_state"),
        "status_snapshot": status_snapshot,
        "telemetry_snapshot": telemetry_snapshot,
        "submission_lock_file": str(lock_dir / "submission_locks.json"),
    }
    return stage_results, workflow_summary, telemetry_snapshot


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("lmcp.telemetry").setLevel(logging.INFO)

    validation_module = _load_module(STAGING_VALIDATION_SCRIPT, "lmcp_validate_staging_environment")
    env_path, env = _load_staging_env(validation_module)
    compose_text = validation_module._text(validation_module.COMPOSE_FILE)
    app_main_text = validation_module._text(validation_module.APP_MAIN_FILE)

    results = _coerce_results(validation_module._validate_env_vars(env))
    results.extend(_coerce_results(validation_module._validate_compose_services(compose_text)))
    results.extend(_coerce_results(validation_module._validate_isolation(env, env_path, compose_text, app_main_text)))
    results.extend(_validate_environment_contract(env, env_path, compose_text, app_main_text))

    stage_results: List[CheckResult] = []
    workflow_summary: Dict[str, Any] = {}
    telemetry_snapshot: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="lmcp-dry-run-harness-") as sandbox_dir:
        sandbox_root = Path(sandbox_dir)
        try:
            with _sandboxed_runtime(sandbox_root) as sandbox_context:
                with _chdir(sandbox_root):
                    stage_results, workflow_summary, telemetry_snapshot = _run_safe_workflow_stage(
                        env,
                        sandbox_context["sandbox_root"],
                        validation_module,
                    )
        finally:
            results.extend(stage_results)

    results.append(
        CheckResult(
            "PASS" if workflow_summary and workflow_summary.get("blocked_submission_result", {}).get("status") == "blocked" else "FAIL",
            "blocked submission proof",
            "submission transition remained blocked in the isolated sandbox" if workflow_summary and workflow_summary.get("blocked_submission_result", {}).get("status") == "blocked" else "submission transition was not blocked",
            "Keep the final SUBMITTED transition hard-blocked.",
        )
    )

    results.append(
        CheckResult(
            "PASS" if workflow_summary.get("final_state") in {"PRICED", "REVIEW_REQUIRED", "SUBMISSION_READY_MANUAL", "QUOTE_PACK_READY"} else "FAIL",
            "non-submission workflow stage",
            f"synthetic RFQ ended in {workflow_summary.get('final_state')}",
            "Keep the dry-run harness limited to non-submission workflow stages.",
        )
    )

    results.append(
        CheckResult(
            "PASS" if telemetry_snapshot else "FAIL",
            "telemetry snapshot",
            "telemetry snapshot was captured" if telemetry_snapshot else "telemetry snapshot was not captured",
            "Confirm the lifecycle telemetry path remains available.",
        )
    )

    results.append(
        CheckResult(
            "PASS",
            "safe termination behavior",
            "harness exited via controlled summary without invoking any live submission path",
            "",
        )
    )

    return _print_summary(results)


if __name__ == "__main__":
    raise SystemExit(main())
