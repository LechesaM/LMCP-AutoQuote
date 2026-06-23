#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import logging
import os
import sys
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
STAGING_VALIDATION_SCRIPT = ROOT_DIR / "scripts" / "validate_staging_environment.py"
REHEARSAL_RUNTIME_DIR = ROOT_DIR / "runtime" / "staging" / "rehearsals"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.dont_write_bytecode = True


@dataclass
class CheckResult:
    level: str
    name: str
    message: str
    remediation: str = ""


@dataclass
class ScenarioResult:
    name: str
    status: str
    checks: List[CheckResult] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    telemetry_events: List[Dict[str, Any]] = field(default_factory=list)
    evidence_dir: str = ""


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


@contextlib.contextmanager
def _temporary_environ(updates: Mapping[str, str]) -> Iterator[None]:
    previous: Dict[str, Optional[str]] = {}
    try:
        for key, value in updates.items():
            previous[key] = os.environ.get(key)
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


def _level_counts(results: Iterable[CheckResult]) -> Dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for result in results:
        counts[result.level] = counts.get(result.level, 0) + 1
    return counts


def _scenario_status(checks: Iterable[CheckResult]) -> str:
    levels = _level_counts(checks)
    if levels["FAIL"]:
        return "FAIL"
    if levels["WARN"]:
        return "WARN"
    return "PASS"


def _print_summary(results: List[CheckResult]) -> int:
    counts = _level_counts(results)
    print(f"PASS: {counts['PASS']}  WARN: {counts['WARN']}  FAIL: {counts['FAIL']}")
    print("")
    for result in results:
        print(f"[{result.level}] {result.name}: {result.message}")
        if result.level != "PASS" and result.remediation:
            print(f"  Remediation: {result.remediation}")
    print("")
    if counts["FAIL"]:
        print("Operational rehearsal failed.")
        return 1
    if counts["WARN"]:
        print("Operational rehearsal passed with warnings.")
    else:
        print("Operational rehearsal passed.")
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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _submission_locks_path(runtime_dir: Path) -> Path:
    return runtime_dir / "go_live_guards" / "submission_locks.json"


def _load_lock_items(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _save_lock_items(path: Path, items: List[Dict[str, Any]], limit: int = 5000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, items[-limit:])


class _GuardShim:
    def create_submission_lock(
        self,
        buyer_rfq_number: str,
        quote_number: str = "",
        reason: str = "submission_completed_or_in_progress",
        metadata: Optional[Dict[str, Any]] = None,
        runtime_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        runtime_root = Path(runtime_dir or ROOT_DIR / "runtime")
        lock_file = _submission_locks_path(runtime_root)
        item = {
            "buyer_rfq_number": str(buyer_rfq_number or "").strip(),
            "quote_number": str(quote_number or "").strip(),
            "reason": reason,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        locks = _load_lock_items(lock_file)
        for existing in locks:
            if (
                str(existing.get("buyer_rfq_number") or "").strip() == item["buyer_rfq_number"]
                and str(existing.get("quote_number") or "").strip() == item["quote_number"]
            ):
                return existing
        locks.append(item)
        _save_lock_items(lock_file, locks)
        return item

    def has_submission_lock(self, buyer_rfq_number: str, quote_number: str = "", runtime_dir: Optional[str] = None) -> bool:
        runtime_root = Path(runtime_dir or ROOT_DIR / "runtime")
        lock_file = _submission_locks_path(runtime_root)
        buyer_rfq_number = str(buyer_rfq_number or "").strip()
        quote_number = str(quote_number or "").strip()
        for item in _load_lock_items(lock_file):
            if str(item.get("buyer_rfq_number") or "").strip() == buyer_rfq_number:
                if not quote_number or str(item.get("quote_number") or "").strip() == quote_number:
                    return True
        return False

    def get_guard_summary(self, limit: int = 80, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
        runtime_root = Path(runtime_dir or ROOT_DIR / "runtime")
        lock_file = _submission_locks_path(runtime_root)
        locks = _load_lock_items(lock_file)
        return {
            "status": "ok",
            "summary": {
                "submission_locks": len(locks),
                "operator_rejections": 0,
                "paused_sources": 0,
                "guard_events": 0,
            },
            "submission_locks": list(reversed(locks[-limit:])),
            "operator_rejections": [],
            "paused_sources": [],
            "recent_guard_events": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


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
def _sandboxed_runtime(sandbox_root: Path) -> Iterator[Dict[str, Any]]:
    import app.operations.structured_logging as telemetry_mod
    import app.services.real_profit_pricing_service as pricing_mod
    import app.services.rfq_lifecycle_service as lifecycle_mod
    import app.services.rfq_state_store as state_store_mod
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
            "telemetry_mod": telemetry_mod,
            "guard_mod": _GuardShim(),
            "lifecycle_mod": lifecycle_mod,
            "state_store_mod": state_store_mod,
            "pricing_mod": pricing_mod,
            "control_mod": control_mod,
            "sandbox_root": sandbox_root,
            "sandbox_runtime": sandbox_runtime,
        }
    finally:
        for module, name, value in reversed(original_values):
            setattr(module, name, value)


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
            "database URLs point at isolated staging PostgreSQL" if db_ok else "database URLs are not isolated to staging PostgreSQL",
            "Set LMCP_DATABASE_URL and DATABASE_URL to the staging PostgreSQL service and database name.",
        )
    )

    redis_urls = [env.get("REDIS_URL", ""), env.get("CELERY_BROKER_URL", ""), env.get("CELERY_RESULT_BACKEND", "")]
    redis_ok = all(url == "redis://redis:6379/0" for url in redis_urls if url)
    results.append(
        CheckResult(
            "PASS" if redis_ok else "FAIL",
            "staging Redis isolation",
            "queue URLs point at the staging Redis service" if redis_ok else "queue URLs do not point at the isolated staging Redis service",
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
    runtime_ok = all(env.get(name, "").startswith("/app/runtime/staging") for name in runtime_prefixes if env.get(name))
    results.append(
        CheckResult(
            "PASS" if runtime_ok else "FAIL",
            "runtime storage isolation",
            "runtime artifacts are scoped to /app/runtime/staging" if runtime_ok else "one or more runtime artifact paths escape the staging runtime directory",
            "Move all staging runtime paths under /app/runtime/staging.",
        )
    )

    telemetry_ok = env.get("LMCP_OBSERVABILITY_ENABLED") == "1" and "prometheus:" in compose_text and "grafana:" in compose_text
    results.append(
        CheckResult(
            "PASS" if telemetry_ok else "FAIL",
            "telemetry configuration presence",
            "telemetry is enabled and staging telemetry services are declared" if telemetry_ok else "telemetry settings or services are missing",
            "Keep LMCP_OBSERVABILITY_ENABLED=1 and ensure Prometheus/Grafana services remain declared.",
        )
    )

    endpoint_ok = "app.main:app" in env.get("LMCP_APP_ENTRYPOINT", "") and '"/health"' in app_main_text and '"/status"' in app_main_text
    results.append(
        CheckResult(
            "PASS" if endpoint_ok else "FAIL",
            "health/status endpoint configuration",
            "backend entrypoint and health/status routes are configured" if endpoint_ok else "backend entrypoint or health/status routes are missing",
            "Keep LMCP_APP_ENTRYPOINT on app.main:app and preserve /health and /status in app/main.py.",
        )
    )

    no_prod_db = all("production" not in env.get(name, "").lower() and "lmcp:lmcp@" not in env.get(name, "") for name in ("LMCP_DATABASE_URL", "DATABASE_URL") if env.get(name))
    results.append(
        CheckResult(
            "PASS" if no_prod_db else "FAIL",
            "no production DB URLs",
            "staging config does not reference production database URLs" if no_prod_db else "a production database URL pattern was detected",
            "Replace any production database URL with the staging PostgreSQL URL.",
        )
    )

    no_prod_queue = all("production" not in env.get(name, "").lower() and "localhost" not in env.get(name, "").lower() for name in ("REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND") if env.get(name))
    results.append(
        CheckResult(
            "PASS" if no_prod_queue else "FAIL",
            "no production queue hosts",
            "staging queue URLs do not target production hosts" if no_prod_queue else "a production or localhost queue host was detected",
            "Point all queue URLs at the isolated staging Redis service.",
        )
    )

    no_prod_creds = all("production" not in env.get(name, "").lower() for name in ("LMCP_OPERATOR_AUTH_DB_PATH", "LMCP_RUNTIME_DIR", "PORTAL_ISOLATION_STATE_FILE") if env.get(name))
    results.append(
        CheckResult(
            "PASS" if no_prod_creds else "FAIL",
            "no production credential paths",
            "credential and runtime paths are staging-scoped" if no_prod_creds else "a production credential or runtime path was detected",
            "Move credential and runtime paths under /app/runtime/staging.",
        )
    )

    backend_ok = "uvicorn" in compose_text and "app.main:app" in compose_text and "/health" in compose_text
    results.append(
        CheckResult(
            "WARN" if not backend_ok else "PASS",
            "backend command and healthcheck",
            "backend command or healthcheck matches the expected staging pattern" if backend_ok else "backend command or healthcheck does not match the expected staging pattern",
            "Keep the backend command on uvicorn app.main:app and the healthcheck on /health.",
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


def _validate_compose_services(compose_text: str) -> List[CheckResult]:
    required_services = ["backend:", "frontend:", "worker:", "operations-worker:", "beat:", "postgres:", "redis:", "prometheus:", "grafana:"]
    missing = [service.rstrip(":") for service in required_services if service not in compose_text]
    return [
        CheckResult(
            "PASS" if not missing else "FAIL",
            "required staging services",
            "all required staging services are declared" if not missing else f"missing staging services: {', '.join(missing)}",
            "Add the missing services to docker-compose.staging.yml.",
        )
    ]


def _create_lock_guard(
    guard_mod: Any,
    sandbox_runtime: Path,
    rfq_id: str,
    *,
    quote_number: str = "",
    reason: str = "operational_rehearsal_lock",
) -> Dict[str, Any]:
    return guard_mod.create_submission_lock(
        rfq_id,
        quote_number=quote_number,
        reason=reason,
        metadata={"mode": "operational_rehearsal", "sandbox_runtime": str(sandbox_runtime)},
        runtime_dir=str(sandbox_runtime),
    )


def _lock_checks(guard_mod: Any, sandbox_runtime: Path, rfq_id: str) -> List[CheckResult]:
    lock_file = sandbox_runtime / "go_live_guards" / "submission_locks.json"
    matching = guard_mod.has_submission_lock(rfq_id, runtime_dir=str(sandbox_runtime))
    mismatched = guard_mod.has_submission_lock("OTHER-RFQ", runtime_dir=str(sandbox_runtime))
    return [
        CheckResult(
            "PASS" if matching and not mismatched and _lock_file_contains_lock(lock_file, rfq_id) else "FAIL",
            "submission lock verification",
            "submission lock was present before rehearsal execution" if matching else "submission lock was not present before rehearsal execution",
            "Ensure the rehearsal runner creates and verifies a staging-only submission lock before processing.",
        )
    ]


def _seed_rfq_item(store: Any, rfq_id: str, state: str, *, title: str, updated_at: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = updated_at or datetime.now(timezone.utc).isoformat()
    item = {
        "rfq_id": rfq_id,
        "buyer_rfq_number": rfq_id,
        "buyer_name": "Staging Buyer",
        "title": title,
        "description": title,
        "source": "staging_rehearsal",
        "current_state": state,
        "previous_state": "",
        "created_at": now,
        "updated_at": now,
        "qualification_score": 95,
        "estimated_profit": 50000,
        "estimated_margin": 30,
        "document_confidence_score": 0.95,
        "buyer_pack_downloaded": True,
        "buyer_pack_verified": True,
        "document_paths": [],
        "document_urls": ["https://example.invalid/rehearsal.pdf"],
        "audit_log": [
            {
                "at": now,
                "event": "seeded_rehearsal_item",
                "from_state": "",
                "to_state": state,
                "reason": "controlled_operational_rehearsal",
            }
        ],
    }
    if extra:
        item.update(extra)
    store.upsert_item(item)
    return item


def _load_state_snapshot(store: Any) -> Dict[str, Any]:
    try:
        return store.read()
    except Exception:
        return {"version": "unknown", "items": {}}


def _scenario_normal_rehearsal(
    env: Dict[str, str],
    sandbox_root: Path,
    sandbox_runtime: Path,
    context: Dict[str, Any],
    evidence_dir: Path,
) -> ScenarioResult:
    from app.operations.structured_logging import (
        generate_correlation_id,
        log_operation_event,
        log_rfq_lifecycle_event,
        log_request_event,
        log_worker_event,
        observability_context,
    )
    from app.services.rfq_lifecycle_service import RfqLifecycleService
    from app.services.rfq_state_store import RfqStateStore, utc_now_iso

    guard_mod = context["guard_mod"]
    telemetry_mod = context["telemetry_mod"]
    store = RfqStateStore(state_file=sandbox_runtime / "rfq_lifecycle" / "rfqs.json")
    lifecycle = RfqLifecycleService(store)
    rfq_id = "REHEARSAL-NORMAL-001"
    trace_id = generate_correlation_id("trace")
    request_id = generate_correlation_id("req")
    operator_id = "staging-rehearsal-operator"
    checks: List[CheckResult] = []
    telemetry_events: List[Dict[str, Any]] = []

    seed_lock = _create_lock_guard(guard_mod, sandbox_runtime, rfq_id, reason="normal_rehearsal_guard")
    checks.extend(_lock_checks(guard_mod, sandbox_runtime, rfq_id))

    with observability_context(
        request_id=request_id,
        trace_id=trace_id,
        rfq_id=rfq_id,
        workflow_stage="normal_rehearsal",
        operator_id=operator_id,
    ):
        telemetry_events.append(
            log_operation_event(
                "operational_rehearsal",
                "normal_rehearsal_started",
                scenario="normal_rfq",
                environment=env.get("LMCP_ENV", "staging"),
                sandbox_root=str(sandbox_root),
            )
        )
        telemetry_events.append(
            log_worker_event(
                "heartbeat",
                "rehearsal_worker_heartbeat",
                worker_id="rehearsal-worker-normal",
                queue_name="staging-validation",
                status="healthy",
                retries=0,
                environment=env.get("LMCP_ENV", "staging"),
            )
        )
        telemetry_events.append(
            log_request_event(
                "POST",
                "/rehearsals/normal",
                status_code=202,
                duration_ms=2.1,
                request_id=request_id,
                trace_id=trace_id,
                environment=env.get("LMCP_ENV", "staging"),
            )
        )

        ingest_result = lifecycle.ingest(
            {
                "source": "staging_operational_rehearsal",
                "items": [
                    {
                        "rfq_id": rfq_id,
                        "buyer_name": "Staging Buyer",
                        "title": "Supply and delivery of office stationery",
                        "description": "Controlled operational rehearsal only",
                        "current_state": "DISCOVERED",
                        "qualification_score": 95,
                        "estimated_profit": 50000,
                        "estimated_margin": 30,
                        "document_confidence_score": 0.95,
                        "buyer_pack_downloaded": True,
                        "buyer_pack_verified": True,
                        "document_urls": ["https://example.invalid/rehearsal.pdf"],
                        "document_paths": [str(sandbox_root / "inputs" / "rehearsal.pdf")],
                        "source_payload": {"submission_method": "email"},
                    }
                ],
            }
        )
        checks.append(
            CheckResult(
                "PASS" if ingest_result.get("status") == "ok" and int(ingest_result.get("ingested_count") or 0) >= 1 else "FAIL",
                "normal rehearsal ingest",
                f"ingest completed with {ingest_result.get('ingested_count', 0)} item(s)",
                "Ensure the synthetic RFQ payload is accepted by the lifecycle ingest stage.",
            )
        )

        state = store.read()
        item = state.get("items", {}).get(rfq_id, {})
        if isinstance(item, dict):
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
                    "document_paths": [str(sandbox_root / "inputs" / "rehearsal.pdf")],
                    "document_urls": ["https://example.invalid/rehearsal.pdf"],
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
        current_state = str(current_item.get("current_state") or "")
        checks.append(
            CheckResult(
                "PASS" if advance_result.get("status") == "ok" and current_state in {"PRICED", "REVIEW_REQUIRED", "SUBMISSION_READY_MANUAL", "QUOTE_PACK_READY"} else "FAIL",
                "normal rehearsal workflow stage",
                f"advance_parsed completed with state {current_state}",
                "Ensure the synthetic RFQ can progress to a non-submission stage inside the isolated sandbox.",
            )
        )
        telemetry_events.append(
            log_rfq_lifecycle_event(
                "workflow_state_transition",
                "Synthetic RFQ advanced through a controlled rehearsal stage",
                rfq_id=rfq_id,
                workflow_stage=current_state or "DOCUMENTS_PARSED",
                status="ok",
                reason=str((advance_result.get("items") or [{}])[0].get("reason") if isinstance(advance_result.get("items"), list) and advance_result.get("items") else ""),
                details=advance_result,
            )
        )

        blocked_submission = lifecycle.advance(rfq_id, target_state="SUBMITTED", note="operational_rehearsal_block_check")
        checks.append(
            CheckResult(
                "PASS" if blocked_submission.get("status") == "blocked" and blocked_submission.get("reason") == "unsafe_final_submission_blocked_without_policy_control" else "FAIL",
                "submission protection",
                "attempt to advance into SUBMITTED was blocked" if blocked_submission.get("status") == "blocked" else "submission advance was not blocked",
                "Keep the lifecycle submission guard hard-blocking SUBMITTED transitions.",
            )
        )
        telemetry_events.append(
            log_rfq_lifecycle_event(
                "blocked_transition",
                "Submission transition blocked during normal rehearsal",
                rfq_id=rfq_id,
                workflow_stage=current_state or "DOCUMENTS_PARSED",
                status="blocked",
                reason=str(blocked_submission.get("reason") or "blocked"),
                details=blocked_submission,
            )
        )

        telemetry_snapshot = lifecycle.telemetry()
        health_snapshot = lifecycle.health_report()
        status_snapshot = lifecycle.status()
        safety_guard = lifecycle.submission_safety_guard()
        checks.append(
            CheckResult(
                "PASS"
                if isinstance(telemetry_snapshot, dict)
                and isinstance(health_snapshot, dict)
                and isinstance(status_snapshot, dict)
                and isinstance(safety_guard, dict)
                else "FAIL",
                "normal rehearsal telemetry",
                f"telemetry={telemetry_snapshot.get('status')} health={health_snapshot.get('status')} status={status_snapshot.get('status')}",
                "Confirm the lifecycle service can produce telemetry, health, and status snapshots in staging.",
            )
        )

    artifacts = {
        "seed_lock": seed_lock,
        "ingest_result": ingest_result,
        "advance_result": advance_result,
        "blocked_submission_result": blocked_submission,
        "final_state": current_state,
        "telemetry_snapshot": telemetry_snapshot,
        "health_snapshot": health_snapshot,
        "status_snapshot": status_snapshot,
        "safety_guard": safety_guard,
    }
    _write_json(evidence_dir / "normal_rehearsal.json", {"scenario": "normal_rfq", **artifacts, "telemetry_events": telemetry_events})

    return ScenarioResult(
        name="normal_rfq",
        status=_scenario_status(checks),
        checks=checks,
        artifacts=artifacts,
        telemetry_events=telemetry_events,
        evidence_dir=str(evidence_dir),
    )


def _scenario_retry_rehearsal(
    env: Dict[str, str],
    sandbox_root: Path,
    sandbox_runtime: Path,
    context: Dict[str, Any],
    evidence_dir: Path,
) -> ScenarioResult:
    from app.operations.structured_logging import generate_correlation_id, log_operation_event, log_worker_event, observability_context
    from app.services.rfq_recovery_service import RfqRecoveryService
    from app.services.rfq_state_store import RfqStateStore

    guard_mod = context["guard_mod"]
    rfq_id_retry = "REHEARSAL-RETRY-001"
    rfq_id_exhausted = "REHEARSAL-RETRY-EXHAUSTED"
    checks: List[CheckResult] = []
    telemetry_events: List[Dict[str, Any]] = []

    store = RfqStateStore(state_file=sandbox_runtime / "rfq_lifecycle" / "rfqs.json")
    recovery = RfqRecoveryService(store)
    _seed_rfq_item(store, rfq_id_retry, "FAILED", title="Retry rehearsal RFQ", extra={"retries": 0, "max_retries": 2, "failure_reason": "retry_rehearsal_timeout"})
    _seed_rfq_item(store, rfq_id_exhausted, "FAILED", title="Exhausted retry rehearsal RFQ", extra={"retries": 3, "max_retries": 3, "failure_reason": "retry_rehearsal_exhausted"})
    _create_lock_guard(guard_mod, sandbox_runtime, rfq_id_retry, reason="retry_rehearsal_guard")
    checks.extend(_lock_checks(guard_mod, sandbox_runtime, rfq_id_retry))

    with observability_context(
        request_id=generate_correlation_id("req"),
        trace_id=generate_correlation_id("trace"),
        rfq_id=rfq_id_retry,
        workflow_stage="retry_rehearsal",
        operator_id="staging-rehearsal-operator",
    ):
        telemetry_events.append(
            log_operation_event(
                "operational_rehearsal",
                "retry_rehearsal_started",
                scenario="retry",
                environment=env.get("LMCP_ENV", "staging"),
            )
        )
        telemetry_events.append(
            log_worker_event(
                "heartbeat",
                "rehearsal_worker_heartbeat",
                worker_id="rehearsal-worker-retry",
                queue_name="retry_queue",
                status="healthy",
                retries=1,
                environment=env.get("LMCP_ENV", "staging"),
            )
        )

        retry_result = recovery.retry_failed()
        checks.append(
            CheckResult(
                "PASS" if int(retry_result.get("retried_count") or 0) >= 1 else "FAIL",
                "retry recovery",
                f"retried_count={retry_result.get('retried_count', 0)} exhausted_count={retry_result.get('exhausted_count', 0)}",
                "Ensure failed RFQs can be retried when retry budgets remain.",
            )
        )
        checks.append(
            CheckResult(
                "PASS" if int(retry_result.get("exhausted_count") or 0) >= 1 else "FAIL",
                "retry exhaustion visibility",
                f"exhausted_count={retry_result.get('exhausted_count', 0)}",
                "Seed exhausted retry records and surface them as dead-letter candidates.",
            )
        )

        health_summary = recovery.worker_health_summary()
        checks.append(
            CheckResult(
                "PASS" if isinstance(health_summary, dict) and int(health_summary.get("failed_items") or 0) >= 0 else "FAIL",
                "retry worker health summary",
                f"queue_ready={health_summary.get('queue_ready')} failed_items={health_summary.get('failed_items')}",
                "Keep the worker health summary available for retry and recovery validation.",
            )
        )

    artifacts = {
        "retry_result": retry_result,
        "worker_health_summary": health_summary,
        "retried_items": retry_result.get("retried_items", []),
        "exhausted_items": retry_result.get("exhausted_items", []),
    }
    _write_json(evidence_dir / "retry_rehearsal.json", {"scenario": "retry_rehearsal", **artifacts, "telemetry_events": telemetry_events})
    return ScenarioResult(
        name="retry_rehearsal",
        status=_scenario_status(checks),
        checks=checks,
        artifacts=artifacts,
        telemetry_events=telemetry_events,
        evidence_dir=str(evidence_dir),
    )


def _scenario_queue_congestion_rehearsal(
    env: Dict[str, str],
    sandbox_root: Path,
    sandbox_runtime: Path,
    context: Dict[str, Any],
    evidence_dir: Path,
) -> ScenarioResult:
    from app.operations.structured_logging import generate_correlation_id, log_operation_event, log_rfq_lifecycle_event, log_worker_event, observability_context
    from app.services.rfq_lifecycle_service import RfqLifecycleService
    from app.services.rfq_state_store import RfqStateStore

    guard_mod = context["guard_mod"]
    store = RfqStateStore(state_file=sandbox_runtime / "rfq_lifecycle" / "rfqs.json")
    lifecycle = RfqLifecycleService(store)
    rfq_ids = [f"REHEARSAL-CONGEST-{idx:03d}" for idx in range(1, 16)]
    checks: List[CheckResult] = []
    telemetry_events: List[Dict[str, Any]] = []

    for index, rfq_id in enumerate(rfq_ids, start=1):
        state = "DOCUMENTS_PARSED" if index % 2 else "PRICED"
        updated_at = (datetime.now(timezone.utc) - timedelta(minutes=30 + index)).isoformat()
        _seed_rfq_item(
            store,
            rfq_id,
            state,
            title=f"Queue congestion rehearsal RFQ {index}",
            updated_at=updated_at,
            extra={"document_paths": [str(sandbox_root / "inputs" / f"{rfq_id}.pdf")]},
        )

    _create_lock_guard(guard_mod, sandbox_runtime, rfq_ids[0], reason="queue_congestion_rehearsal_guard")
    checks.extend(_lock_checks(guard_mod, sandbox_runtime, rfq_ids[0]))

    with _temporary_environ({
        "RFQ_QUEUE_BACKLOG_WARNING_DEPTH": "5",
        "RFQ_STALLED_TASK_SECONDS": "1",
        "RFQ_TASK_TIMEOUT_SECONDS": "1",
        "RFQ_CPU_PRESSURE_PERCENT": "99.9",
        "RFQ_MEMORY_PRESSURE_PERCENT": "99.9",
    }):
        with observability_context(
            request_id=generate_correlation_id("req"),
            trace_id=generate_correlation_id("trace"),
            rfq_id=rfq_ids[0],
            workflow_stage="queue_congestion_rehearsal",
            operator_id="staging-rehearsal-operator",
        ):
            telemetry_events.append(
                log_operation_event(
                    "operational_rehearsal",
                    "queue_congestion_rehearsal_started",
                    scenario="queue_congestion",
                    environment=env.get("LMCP_ENV", "staging"),
                    rehearsal_rfq_count=len(rfq_ids),
                )
            )
            telemetry_events.append(
                log_worker_event(
                    "heartbeat",
                    "rehearsal_worker_heartbeat",
                    worker_id="rehearsal-worker-queue",
                    queue_name="pricing_queue",
                    status="degraded",
                    retries=2,
                    environment=env.get("LMCP_ENV", "staging"),
                )
            )

            telemetry_snapshot = lifecycle.telemetry()
            mission_snapshot = lifecycle.mission_control_summary()
            backlog = telemetry_snapshot.get("queue_backlog") if isinstance(telemetry_snapshot, dict) else {}
            queue_backpressure = mission_snapshot.get("queue_backpressure") if isinstance(mission_snapshot, dict) else {}

            checks.append(
                CheckResult(
                    "PASS" if isinstance(backlog, dict) and int(backlog.get("total_backlog") or 0) >= 5 else "FAIL",
                    "queue congestion detection",
                    f"total_backlog={backlog.get('total_backlog', 0)} warning_threshold={backlog.get('warning_threshold', 0)}",
                    "Seed enough queued RFQs to exceed the rehearsal backlog threshold.",
                )
            )
            checks.append(
                CheckResult(
                    "PASS" if isinstance(queue_backpressure, dict) and bool(queue_backpressure.get("active")) else "WARN",
                    "queue pressure visibility",
                    f"queue_backpressure_active={queue_backpressure.get('active')}",
                    "Keep queue backlog and bottleneck summaries visible in Mission Control.",
                )
            )
            telemetry_events.append(
                log_rfq_lifecycle_event(
                    "queue_pressure",
                    "Queue congestion rehearsal telemetry captured",
                    rfq_id=rfq_ids[0],
                    workflow_stage="queue_congestion_rehearsal",
                    status="warn" if not bool(queue_backpressure.get("active")) else "ok",
                    details={"queue_backlog": backlog, "queue_backpressure": queue_backpressure},
                )
            )

    artifacts = {
        "rfq_ids": rfq_ids,
        "telemetry_snapshot": telemetry_snapshot,
        "mission_control_snapshot": mission_snapshot,
    }
    _write_json(evidence_dir / "queue_congestion_rehearsal.json", {"scenario": "queue_congestion_rehearsal", **artifacts, "telemetry_events": telemetry_events})
    return ScenarioResult(
        name="queue_congestion_rehearsal",
        status=_scenario_status(checks),
        checks=checks,
        artifacts=artifacts,
        telemetry_events=telemetry_events,
        evidence_dir=str(evidence_dir),
    )


def _scenario_worker_recovery_rehearsal(
    env: Dict[str, str],
    sandbox_root: Path,
    sandbox_runtime: Path,
    context: Dict[str, Any],
    evidence_dir: Path,
) -> ScenarioResult:
    from app.operations.structured_logging import generate_correlation_id, log_operation_event, log_rfq_lifecycle_event, log_worker_event, observability_context
    from app.services.rfq_lifecycle_service import RfqLifecycleService
    from app.services.rfq_state_store import RfqStateStore

    guard_mod = context["guard_mod"]
    store = RfqStateStore(state_file=sandbox_runtime / "rfq_lifecycle" / "rfqs.json")
    lifecycle = RfqLifecycleService(store)
    rfq_ids = [f"REHEARSAL-STALE-{idx:03d}" for idx in range(1, 4)]
    checks: List[CheckResult] = []
    telemetry_events: List[Dict[str, Any]] = []

    stale_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=180)).isoformat()
    for rfq_id in rfq_ids:
        _seed_rfq_item(
            store,
            rfq_id,
            "PRICED",
            title=f"Worker recovery rehearsal RFQ {rfq_id}",
            updated_at=stale_timestamp,
            extra={"failure_reason": "stale_recovery_rehearsal"},
        )

    _create_lock_guard(guard_mod, sandbox_runtime, rfq_ids[0], reason="worker_recovery_rehearsal_guard")
    checks.extend(_lock_checks(guard_mod, sandbox_runtime, rfq_ids[0]))

    with _temporary_environ({
        "RFQ_STALLED_TASK_SECONDS": "1",
        "RFQ_QUEUE_BACKLOG_WARNING_DEPTH": "5",
        "RFQ_TASK_TIMEOUT_SECONDS": "1",
    }):
        with observability_context(
            request_id=generate_correlation_id("req"),
            trace_id=generate_correlation_id("trace"),
            rfq_id=rfq_ids[0],
            workflow_stage="worker_recovery_rehearsal",
            operator_id="staging-rehearsal-operator",
        ):
            telemetry_events.append(
                log_operation_event(
                    "operational_rehearsal",
                    "worker_recovery_rehearsal_started",
                    scenario="worker_recovery",
                    environment=env.get("LMCP_ENV", "staging"),
                )
            )
            telemetry_events.append(
                log_worker_event(
                    "heartbeat",
                    "rehearsal_worker_heartbeat",
                    worker_id="rehearsal-worker-recovery",
                    queue_name="retry_queue",
                    status="degraded",
                    retries=0,
                    environment=env.get("LMCP_ENV", "staging"),
                )
            )

            recover_result = lifecycle.recover_stuck(timeout_minutes=60)
            checks.append(
                CheckResult(
                    "PASS" if int(recover_result.get("recovered_count") or 0) >= len(rfq_ids) else "FAIL",
                    "stuck worker recovery",
                    f"recovered_count={recover_result.get('recovered_count', 0)} untouched_count={recover_result.get('untouched_count', 0)}",
                    "Seed stale RFQs and ensure the recovery path promotes them to REVIEW_REQUIRED.",
                )
            )

            recovered_states = [store.get_item(rfq_id).get("current_state") if store.get_item(rfq_id) else "" for rfq_id in rfq_ids]
            checks.append(
                CheckResult(
                    "PASS" if all(state == "REVIEW_REQUIRED" for state in recovered_states) else "FAIL",
                    "stuck state transition",
                    f"recovered_states={recovered_states}",
                    "Recovery should move stale items to REVIEW_REQUIRED for operator review.",
                )
            )

            telemetry_snapshot = lifecycle.telemetry()
            health_snapshot = lifecycle.health_report()
            checks.append(
                CheckResult(
                    "PASS" if isinstance(telemetry_snapshot, dict) and isinstance(health_snapshot, dict) else "FAIL",
                    "worker recovery telemetry",
                    f"telemetry={telemetry_snapshot.get('status')} health={health_snapshot.get('status')}",
                    "Keep telemetry and health reporting available during worker recovery.",
                )
            )
            telemetry_events.append(
                log_rfq_lifecycle_event(
                    "recovery",
                    "Worker recovery rehearsal telemetry captured",
                    rfq_id=rfq_ids[0],
                    workflow_stage="worker_recovery_rehearsal",
                    status="ok",
                    details={"recover_result": recover_result, "telemetry": telemetry_snapshot},
                )
            )

    artifacts = {
        "recover_result": recover_result,
        "telemetry_snapshot": telemetry_snapshot,
        "health_snapshot": health_snapshot,
        "recovered_states": recovered_states,
    }
    _write_json(evidence_dir / "worker_recovery_rehearsal.json", {"scenario": "worker_recovery_rehearsal", **artifacts, "telemetry_events": telemetry_events})
    return ScenarioResult(
        name="worker_recovery_rehearsal",
        status=_scenario_status(checks),
        checks=checks,
        artifacts=artifacts,
        telemetry_events=telemetry_events,
        evidence_dir=str(evidence_dir),
    )


def _scenario_dead_letter_rehearsal(
    env: Dict[str, str],
    sandbox_root: Path,
    sandbox_runtime: Path,
    context: Dict[str, Any],
    evidence_dir: Path,
) -> ScenarioResult:
    from app.operations.structured_logging import generate_correlation_id, log_operation_event, log_rfq_lifecycle_event, log_worker_event, observability_context
    from app.services.rfq_recovery_service import RfqRecoveryService
    from app.services.rfq_state_store import RfqStateStore

    guard_mod = context["guard_mod"]
    store = RfqStateStore(state_file=sandbox_runtime / "rfq_lifecycle" / "rfqs.json")
    recovery = RfqRecoveryService(store)
    rfq_ids = [f"REHEARSAL-DLQ-{idx:03d}" for idx in range(1, 4)]
    checks: List[CheckResult] = []
    telemetry_events: List[Dict[str, Any]] = []

    for rfq_id in rfq_ids:
        _seed_rfq_item(
            store,
            rfq_id,
            "FAILED",
            title=f"Dead-letter rehearsal RFQ {rfq_id}",
            extra={"retries": 3, "max_retries": 3, "failure_reason": "dead_letter_rehearsal_exhausted"},
        )

    _create_lock_guard(guard_mod, sandbox_runtime, rfq_ids[0], reason="dead_letter_rehearsal_guard")
    checks.extend(_lock_checks(guard_mod, sandbox_runtime, rfq_ids[0]))

    with observability_context(
        request_id=generate_correlation_id("req"),
        trace_id=generate_correlation_id("trace"),
        rfq_id=rfq_ids[0],
        workflow_stage="dead_letter_rehearsal",
        operator_id="staging-rehearsal-operator",
    ):
        telemetry_events.append(
            log_operation_event(
                "operational_rehearsal",
                "dead_letter_rehearsal_started",
                scenario="dead_letter",
                environment=env.get("LMCP_ENV", "staging"),
            )
        )
        telemetry_events.append(
            log_worker_event(
                "heartbeat",
                "rehearsal_worker_heartbeat",
                worker_id="rehearsal-worker-dlq",
                queue_name="retry_queue",
                status="degraded",
                retries=3,
                environment=env.get("LMCP_ENV", "staging"),
            )
        )

        retry_result = recovery.retry_failed()
        checks.append(
            CheckResult(
                "PASS" if int(retry_result.get("exhausted_count") or 0) >= len(rfq_ids) else "FAIL",
                "dead-letter exhaustion visibility",
                f"exhausted_count={retry_result.get('exhausted_count', 0)}",
                "Keep exhausted retries visible as dead-letter candidates.",
            )
        )

        worker_health = recovery.worker_health_summary()
        checks.append(
            CheckResult(
                "PASS" if isinstance(worker_health, dict) and int(worker_health.get("failed_items") or 0) >= len(rfq_ids) else "FAIL",
                "dead-letter worker health",
                f"failed_items={worker_health.get('failed_items')} active_items={worker_health.get('active_items')}",
                "Expose failed-item counts in the dead-letter recovery path.",
            )
        )

        telemetry_snapshot = context["lifecycle_mod"].RfqLifecycleService(store).telemetry()
        checks.append(
            CheckResult(
                "PASS" if isinstance(telemetry_snapshot, dict) else "FAIL",
                "dead-letter telemetry",
                f"telemetry_status={telemetry_snapshot.get('status')}",
                "Keep telemetry available even when retry budgets are exhausted.",
            )
        )
        telemetry_events.append(
            log_rfq_lifecycle_event(
                "dead_letter",
                "Dead-letter rehearsal telemetry captured",
                rfq_id=rfq_ids[0],
                workflow_stage="dead_letter_rehearsal",
                status="ok",
                details={"retry_result": retry_result, "worker_health": worker_health},
            )
        )

    dead_letter_candidates = [
        {
            "rfq_id": item.get("rfq_id"),
            "current_state": item.get("current_state"),
            "retries": item.get("retries"),
            "max_retries": item.get("max_retries"),
            "failure_reason": item.get("failure_reason"),
        }
        for item in retry_result.get("exhausted_items", [])
        if isinstance(item, dict)
    ]
    artifacts = {
        "retry_result": retry_result,
        "worker_health": worker_health,
        "telemetry_snapshot": telemetry_snapshot,
        "dead_letter_candidates": dead_letter_candidates,
    }
    _write_json(evidence_dir / "dead_letter_rehearsal.json", {"scenario": "dead_letter_rehearsal", **artifacts, "telemetry_events": telemetry_events})
    return ScenarioResult(
        name="dead_letter_rehearsal",
        status=_scenario_status(checks),
        checks=checks,
        artifacts=artifacts,
        telemetry_events=telemetry_events,
        evidence_dir=str(evidence_dir),
    )


def _scenario_rollback_rehearsal(
    env: Dict[str, str],
    sandbox_root: Path,
    sandbox_runtime: Path,
    context: Dict[str, Any],
    evidence_dir: Path,
) -> ScenarioResult:
    from app.operations.structured_logging import generate_correlation_id, log_operation_event, log_rfq_lifecycle_event, observability_context
    from app.services.rfq_state_store import RfqStateStore

    guard_mod = context["guard_mod"]
    store = RfqStateStore(state_file=sandbox_runtime / "rfq_lifecycle" / "rfqs.json")
    rfq_id = "REHEARSAL-ROLLBACK-001"
    checks: List[CheckResult] = []
    telemetry_events: List[Dict[str, Any]] = []

    _seed_rfq_item(store, rfq_id, "DOCUMENTS_PARSED", title="Rollback rehearsal RFQ")
    _create_lock_guard(guard_mod, sandbox_runtime, rfq_id, reason="rollback_rehearsal_guard")
    checks.extend(_lock_checks(guard_mod, sandbox_runtime, rfq_id))

    before = _load_state_snapshot(store)
    before_item = store.get_item(rfq_id) or {}

    with observability_context(
        request_id=generate_correlation_id("req"),
        trace_id=generate_correlation_id("trace"),
        rfq_id=rfq_id,
        workflow_stage="rollback_rehearsal",
        operator_id="staging-rehearsal-operator",
    ):
        telemetry_events.append(
            log_operation_event(
                "operational_rehearsal",
                "rollback_rehearsal_started",
                scenario="rollback",
                environment=env.get("LMCP_ENV", "staging"),
            )
        )
        mutated = dict(before_item)
        mutated["current_state"] = "REVIEW_REQUIRED"
        mutated["failure_reason"] = "rollback_rehearsal_mutation"
        mutated["updated_at"] = datetime.now(timezone.utc).isoformat()
        if mutated:
            store.upsert_item(mutated)
        mutated_snapshot = store.get_item(rfq_id) or {}

        store.write(before)
        after_restore = _load_state_snapshot(store)
        after_item = store.get_item(rfq_id) or {}
        checks.append(
            CheckResult(
                "PASS" if after_item.get("current_state") == before_item.get("current_state") and after_restore.get("items", {}).get(rfq_id, {}).get("current_state") == before_item.get("current_state") else "FAIL",
                "rollback restoration",
                f"before_state={before_item.get('current_state')} restored_state={after_item.get('current_state')}",
                "Keep rollback rehearsal limited to isolated sandbox state restoration.",
            )
        )
        telemetry_events.append(
            log_rfq_lifecycle_event(
                "rollback",
                "Rollback rehearsal state restored",
                rfq_id=rfq_id,
                workflow_stage="rollback_rehearsal",
                status="ok",
                details={"before": before_item, "mutated": mutated_snapshot, "restored": after_item},
            )
        )

    artifacts = {
        "before_state": before,
        "before_item": before_item,
        "mutated_item": mutated_snapshot,
        "restored_state": after_restore,
        "restored_item": after_item,
    }
    _write_json(evidence_dir / "rollback_rehearsal.json", {"scenario": "rollback_rehearsal", **artifacts, "telemetry_events": telemetry_events})
    return ScenarioResult(
        name="rollback_rehearsal",
        status=_scenario_status(checks),
        checks=checks,
        artifacts=artifacts,
        telemetry_events=telemetry_events,
        evidence_dir=str(evidence_dir),
    )


def _scenario_telemetry_validation_rehearsal(
    env: Dict[str, str],
    sandbox_root: Path,
    sandbox_runtime: Path,
    context: Dict[str, Any],
    evidence_dir: Path,
) -> ScenarioResult:
    from app.operations.structured_logging import (
        generate_correlation_id,
        log_operation_event,
        log_rfq_lifecycle_event,
        log_request_event,
        log_worker_event,
        observability_context,
    )
    from app.services.rfq_lifecycle_service import RfqLifecycleService
    from app.services.rfq_state_store import RfqStateStore

    guard_mod = context["guard_mod"]
    store = RfqStateStore(state_file=sandbox_runtime / "rfq_lifecycle" / "rfqs.json")
    lifecycle = RfqLifecycleService(store)
    rfq_id = "REHEARSAL-TELEMETRY-001"
    checks: List[CheckResult] = []
    telemetry_events: List[Dict[str, Any]] = []

    _seed_rfq_item(store, rfq_id, "SUBMISSION_READY", title="Telemetry rehearsal RFQ")
    _create_lock_guard(guard_mod, sandbox_runtime, rfq_id, reason="telemetry_rehearsal_guard")
    checks.extend(_lock_checks(guard_mod, sandbox_runtime, rfq_id))

    with observability_context(
        request_id=generate_correlation_id("req"),
        trace_id=generate_correlation_id("trace"),
        rfq_id=rfq_id,
        workflow_stage="telemetry_validation_rehearsal",
        operator_id="staging-rehearsal-operator",
    ):
        telemetry_events.append(
            log_operation_event(
                "operational_rehearsal",
                "telemetry_validation_rehearsal_started",
                scenario="telemetry_validation",
                environment=env.get("LMCP_ENV", "staging"),
            )
        )
        telemetry_events.append(
            log_worker_event(
                "heartbeat",
                "rehearsal_worker_heartbeat",
                worker_id="rehearsal-worker-telemetry",
                queue_name="observability_queue",
                status="healthy",
                retries=0,
                environment=env.get("LMCP_ENV", "staging"),
            )
        )
        telemetry_events.append(
            log_request_event(
                "GET",
                "/telemetry/rehearsal",
                status_code=200,
                duration_ms=1.8,
                request_id=generate_correlation_id("req"),
                trace_id=generate_correlation_id("trace"),
                environment=env.get("LMCP_ENV", "staging"),
            )
        )

        telemetry_snapshot = lifecycle.telemetry()
        health_snapshot = lifecycle.health_report()
        status_snapshot = lifecycle.status()
        safety_guard = lifecycle.submission_safety_guard()
        guard_summary = guard_mod.get_guard_summary(runtime_dir=str(sandbox_runtime))
        checks.extend(
            [
                CheckResult(
                    "PASS" if isinstance(telemetry_snapshot, dict) and telemetry_snapshot.get("status") == "ok" else "FAIL",
                    "telemetry snapshot",
                    f"telemetry_status={telemetry_snapshot.get('status')} resilience={telemetry_snapshot.get('system_resilience_score')}",
                    "Keep lifecycle telemetry available for operational rehearsals.",
                ),
                CheckResult(
                    "PASS" if isinstance(health_snapshot, dict) and isinstance(status_snapshot, dict) else "FAIL",
                    "health/status snapshots",
                    f"health_status={health_snapshot.get('status')} status={status_snapshot.get('status')}",
                    "Keep /health and /status compatible with the operational rehearsal surface.",
                ),
                CheckResult(
                    "PASS" if isinstance(safety_guard, dict) and safety_guard.get("final_submit_hard_blocked_by_lifecycle") is True else "FAIL",
                    "submission safety guard",
                    f"final_submit_hard_blocked={safety_guard.get('final_submit_hard_blocked_by_lifecycle')}",
                    "Keep the final submit hard-block active during staging rehearsal.",
                ),
                CheckResult(
                    "PASS" if isinstance(guard_summary, dict) and guard_summary.get("status") == "ok" else "FAIL",
                    "guard summary",
                    f"guard_status={guard_summary.get('status')} submission_locks={guard_summary.get('summary', {}).get('submission_locks', 0)}",
                    "Keep staging-only guard summaries available during rehearsals.",
                ),
            ]
        )
        telemetry_events.append(
            log_rfq_lifecycle_event(
                "telemetry",
                "Telemetry validation rehearsal snapshots captured",
                rfq_id=rfq_id,
                workflow_stage="telemetry_validation_rehearsal",
                status="ok",
                details={"telemetry": telemetry_snapshot, "health": health_snapshot, "status": status_snapshot, "guard_summary": guard_summary},
            )
        )

    artifacts = {
        "telemetry_snapshot": telemetry_snapshot,
        "health_snapshot": health_snapshot,
        "status_snapshot": status_snapshot,
        "safety_guard": safety_guard,
        "guard_summary": guard_summary,
    }
    _write_json(evidence_dir / "telemetry_validation_rehearsal.json", {"scenario": "telemetry_validation_rehearsal", **artifacts, "telemetry_events": telemetry_events})
    return ScenarioResult(
        name="telemetry_validation_rehearsal",
        status=_scenario_status(checks),
        checks=checks,
        artifacts=artifacts,
        telemetry_events=telemetry_events,
        evidence_dir=str(evidence_dir),
    )


SCENARIO_RUNNERS = {
    "normal_rfq": _scenario_normal_rehearsal,
    "retry_rehearsal": _scenario_retry_rehearsal,
    "queue_congestion_rehearsal": _scenario_queue_congestion_rehearsal,
    "worker_recovery_rehearsal": _scenario_worker_recovery_rehearsal,
    "dead_letter_rehearsal": _scenario_dead_letter_rehearsal,
    "rollback_rehearsal": _scenario_rollback_rehearsal,
    "telemetry_validation_rehearsal": _scenario_telemetry_validation_rehearsal,
}


def _run_scenario(
    scenario_name: str,
    env: Dict[str, str],
    run_dir: Path,
) -> ScenarioResult:
    runner = SCENARIO_RUNNERS[scenario_name]
    scenario_dir = run_dir / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"lmcp-operational-{scenario_name}-") as temp_dir:
        sandbox_root = Path(temp_dir)
        with _sandboxed_runtime(sandbox_root) as context:
            with _temporary_environ(
                {
                    "RFQ_QUEUE_BACKLOG_WARNING_DEPTH": "5",
                    "RFQ_STALLED_TASK_SECONDS": "1",
                    "RFQ_TASK_TIMEOUT_SECONDS": "1",
                    "RFQ_CELERY_INSPECT_TIMEOUT": "0.2",
                    "RFQ_CPU_PRESSURE_PERCENT": "99.9",
                    "RFQ_MEMORY_PRESSURE_PERCENT": "99.9",
                }
            ):
                with _chdir(sandbox_root):
                    result = runner(env, sandbox_root, context["sandbox_runtime"], context, scenario_dir)
    return result


def _critical_environment_failures(results: Iterable[CheckResult]) -> bool:
    critical = {
        "required staging variables",
        "dry-run enforcement",
        "final automation disabled",
        "staging DB isolation",
        "staging Redis isolation",
        "runtime storage isolation",
        "telemetry configuration presence",
        "health/status endpoint configuration",
        "no production DB URLs",
        "no production queue hosts",
        "no production credential paths",
    }
    return any(result.level == "FAIL" and result.name in critical for result in results)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run LMCP controlled operational rehearsals in staging-only mode.")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIO_RUNNERS.keys()),
        help="Run only the named rehearsal scenario(s). Repeat to run multiple scenarios.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional rehearsal run identifier used for the evidence directory name.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("lmcp.telemetry").setLevel(logging.INFO)

    validation_module = _load_module(STAGING_VALIDATION_SCRIPT, "lmcp_validate_staging_environment_operational")
    env_path, env = _load_staging_env(validation_module)
    compose_text = validation_module._text(validation_module.COMPOSE_FILE)
    app_main_text = validation_module._text(validation_module.APP_MAIN_FILE)

    env_results = _coerce_results(validation_module.run_validation())
    env_results.extend(_validate_environment_contract(env, env_path, compose_text, app_main_text))

    all_results: List[CheckResult] = list(env_results)
    counts = _level_counts(env_results)
    if _critical_environment_failures(env_results):
        print("PASS: 0  WARN: 0  FAIL: 1")
        print("")
        for result in env_results:
            print(f"[{result.level}] {result.name}: {result.message}")
            if result.level != "PASS" and result.remediation:
                print(f"  Remediation: {result.remediation}")
        print("")
        print("Operational rehearsal aborted before execution because the staging contract failed.")
        return 1

    run_id = args.run_id.strip() or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-operational-{uuid.uuid4().hex[:8]}"
    run_dir = REHEARSAL_RUNTIME_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_text(run_dir / "run_id.txt", run_id)
    _write_json(
        run_dir / "environment_contract.json",
        {
            "env_path": str(env_path),
            "environment": env,
            "staging_validation_counts": counts,
            "critical_checks": [result.__dict__ for result in env_results],
        },
    )

    requested_scenarios = args.scenario or list(SCENARIO_RUNNERS.keys())
    scenario_results: List[ScenarioResult] = []
    for scenario_name in requested_scenarios:
        scenario_result = _run_scenario(scenario_name, env, run_dir)
        scenario_results.append(scenario_result)
        all_results.extend(scenario_result.checks)
        _write_json(
            run_dir / scenario_name / "scenario_summary.json",
            {
                "scenario": scenario_result.name,
                "status": scenario_result.status,
                "checks": [check.__dict__ for check in scenario_result.checks],
                "artifacts": scenario_result.artifacts,
                "telemetry_events": scenario_result.telemetry_events,
                "evidence_dir": scenario_result.evidence_dir,
            },
        )

    summary = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_count": len(scenario_results),
        "scenario_statuses": {result.name: result.status for result in scenario_results},
        "scenario_summaries": [
            {
                "name": result.name,
                "status": result.status,
                "checks": len(result.checks),
                "warnings": sum(1 for check in result.checks if check.level == "WARN"),
                "failures": sum(1 for check in result.checks if check.level == "FAIL"),
                "evidence_dir": result.evidence_dir,
            }
            for result in scenario_results
        ],
        "overall_counts": _level_counts(all_results),
        "environment_contract": {
            "path": str(env_path),
            "staging_validation_passed": not _critical_environment_failures(env_results),
        },
        "dry_run_guarantees": {
            "live_submissions": False,
            "production_queues": False,
            "production_databases": False,
            "irreversible_operations": False,
        },
    }
    _write_json(run_dir / "operational_rehearsal_summary.json", summary)
    _write_text(
        run_dir / "operational_rehearsal_summary.txt",
        "\n".join(
            [
                f"Run ID: {run_id}",
                f"Scenarios: {', '.join(result.name for result in scenario_results)}",
                f"PASS: {summary['overall_counts']['PASS']}  WARN: {summary['overall_counts']['WARN']}  FAIL: {summary['overall_counts']['FAIL']}",
                "",
                *(f"[{result.status}] {result.name}" for result in scenario_results),
            ]
        ),
    )
    _write_json(REHEARSAL_RUNTIME_DIR / "latest_operational_rehearsal.json", summary)
    _write_text(REHEARSAL_RUNTIME_DIR / "latest_operational_rehearsal.txt", run_dir.joinpath("operational_rehearsal_summary.txt").read_text(encoding="utf-8"))

    return _print_summary(all_results)


if __name__ == "__main__":
    raise SystemExit(main())
