from __future__ import annotations

import importlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.stability_guard import StabilityGuard
from app.db.session import test_db_connection
from app.services.pilot_run_log_service import build_pilot_run_report, list_recent_pilot_runs
from app.services.tender_submission_pipeline import TenderSubmissionPipeline

RUNTIME_DIR = Path("runtime")
GUARD_DIR = RUNTIME_DIR / "go_live_guards"
GUARD_DIR.mkdir(parents=True, exist_ok=True)

DUPLICATE_SUBMISSION_FILE = GUARD_DIR / "submission_locks.json"
GUARD_AUDIT_FILE = GUARD_DIR / "guard_events.json"

OPERATOR_DIR = RUNTIME_DIR / "operator_actions"
REJECTION_FILE = OPERATOR_DIR / "operator_rejections.json"
PAUSED_SOURCES_FILE = OPERATOR_DIR / "paused_sources.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_list(path: Path, items: List[Dict[str, Any]], limit: int = 5000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[-limit:], indent=2, default=str))


def is_rfq_rejected(buyer_rfq_number: str) -> bool:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    return any(
        str(x.get("buyer_rfq_number") or "").strip() == buyer_rfq_number
        for x in _load_list(REJECTION_FILE)
    )


def is_source_paused(source_name: str) -> bool:
    source_name = str(source_name or "").strip()
    return any(
        str(x.get("source_name") or "").strip() == source_name
        for x in _load_list(PAUSED_SOURCES_FILE)
    )


def has_submission_lock(buyer_rfq_number: str, quote_number: str = "") -> bool:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    quote_number = str(quote_number or "").strip()

    for item in _load_list(DUPLICATE_SUBMISSION_FILE):
        if str(item.get("buyer_rfq_number") or "").strip() == buyer_rfq_number:
            if not quote_number or str(item.get("quote_number") or "").strip() == quote_number:
                return True
    return False


def create_submission_lock(
    buyer_rfq_number: str,
    quote_number: str = "",
    reason: str = "submission_completed_or_in_progress",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    item = {
        "buyer_rfq_number": str(buyer_rfq_number or "").strip(),
        "quote_number": str(quote_number or "").strip(),
        "reason": reason,
        "metadata": metadata or {},
        "created_at": _now_iso(),
    }

    locks = _load_list(DUPLICATE_SUBMISSION_FILE)

    for existing in locks:
        if (
            str(existing.get("buyer_rfq_number") or "").strip() == item["buyer_rfq_number"]
            and str(existing.get("quote_number") or "").strip() == item["quote_number"]
        ):
            return existing

    locks.append(item)
    _save_list(DUPLICATE_SUBMISSION_FILE, locks)
    return item


def clear_submission_lock(buyer_rfq_number: str, quote_number: str = "") -> Dict[str, Any]:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    quote_number = str(quote_number or "").strip()

    locks = _load_list(DUPLICATE_SUBMISSION_FILE)
    kept = []
    removed = []

    for item in locks:
        same_rfq = str(item.get("buyer_rfq_number") or "").strip() == buyer_rfq_number
        same_quote = not quote_number or str(item.get("quote_number") or "").strip() == quote_number

        if same_rfq and same_quote:
            removed.append(item)
        else:
            kept.append(item)

    _save_list(DUPLICATE_SUBMISSION_FILE, kept)

    return {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "removed": len(removed),
    }


def evaluate_pipeline_guard(payload: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rfq_number = (
        payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("tender_number")
        or payload.get("reference")
        or ""
    )
    quote_number = payload.get("quote_number") or ""
    source_name = payload.get("source_name") or payload.get("source") or ""

    blockers = []

    if is_rfq_rejected(str(buyer_rfq_number)):
        blockers.append("RFQ is rejected by operator and must not be quoted/submitted.")

    if is_source_paused(str(source_name)):
        blockers.append("Source is paused by operator and must not be harvested.")

    if has_submission_lock(str(buyer_rfq_number), str(quote_number)):
        blockers.append("Duplicate submission lock exists for this RFQ/quote.")

    return {
        "status": "ok",
        "allowed": len(blockers) == 0,
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "source_name": source_name,
        "blockers": blockers,
        "warnings": [],
        "checked_at": _now_iso(),
    }


def get_guard_summary(limit: int = 80) -> Dict[str, Any]:
    locks = _load_list(DUPLICATE_SUBMISSION_FILE)
    rejected = _load_list(REJECTION_FILE)
    paused = _load_list(PAUSED_SOURCES_FILE)
    events = _load_list(GUARD_AUDIT_FILE)

    return {
        "status": "ok",
        "summary": {
            "submission_locks": len(locks),
            "operator_rejections": len(rejected),
            "paused_sources": len(paused),
            "guard_events": len(events),
        },
        "submission_locks": list(reversed(locks[-limit:])),
        "operator_rejections": list(reversed(rejected[-limit:])),
        "paused_sources": list(reversed(paused[-limit:])),
        "recent_guard_events": list(reversed(events[-limit:])),
        "updated_at": _now_iso(),
    }


def _build_check(
    name: str,
    status: str,
    summary: str,
    *,
    blocking: bool = False,
    details: Optional[Dict[str, Any]] = None,
    next_action: str = "",
) -> Dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "summary": summary,
        "blocking": blocking,
        "details": details or {},
        "next_action": next_action,
    }


def _load_router_report() -> Dict[str, Any]:
    from app.main import app

    report = getattr(app.state, "router_report", None)
    if isinstance(report, dict):
        return report
    return {"loaded": [], "failures": [], "duplicates": []}


def _load_startup_degraded_state() -> Dict[str, Any]:
    try:
        from app.main import app
    except Exception:
        return {"degraded": False, "error": ""}
    state = getattr(app, "state", None)
    return {
        "degraded": bool(getattr(state, "database_startup_degraded", False)),
        "error": str(getattr(state, "database_startup_error", "") or ""),
    }


def _storage_targets() -> List[Path]:
    return [
        settings.runtime_dir,
        settings.monthly_quotes_dir,
        settings.log_dir,
        settings.submission_proofs_dir,
        settings.portal_submission_dir,
        settings.final_submission_dir,
        settings.proof_center_dir,
    ]


def _check_storage_writable() -> Dict[str, Any]:
    writable: List[str] = []
    failures: List[Dict[str, str]] = []
    for directory in _storage_targets():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".lmcp_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            writable.append(str(directory))
        except Exception as exc:
            failures.append({"path": str(directory), "error": str(exc)})
    if failures:
        return _build_check(
            "storage_folders_writable",
            "blocked",
            "One or more storage folders are not writable.",
            blocking=True,
            details={"writable": writable, "failures": failures},
            next_action="Fix filesystem permissions for the reported storage folders.",
        )
    return _build_check(
        "storage_folders_writable",
        "ready",
        "All required storage folders are writable.",
        details={"writable": writable},
    )


def _check_required_env_vars() -> Dict[str, Any]:
    guard = StabilityGuard()
    try:
        result = guard.validate_environment()
    except Exception as exc:
        return _build_check(
            "required_env_vars_configured",
            "blocked",
            str(exc),
            blocking=True,
            details={"configured": False},
            next_action="Configure the required environment variables and restart the API.",
        )
    missing_recommended = list(result.get("missing_recommended") or [])
    if missing_recommended:
        return _build_check(
            "required_env_vars_configured",
            "warning",
            "Required environment variables are configured, but recommended values are missing.",
            details=result,
            next_action=f"Set recommended environment variables: {', '.join(missing_recommended)}.",
        )
    return _build_check(
        "required_env_vars_configured",
        "ready",
        "Required environment variables are configured.",
        details=result,
    )


def _check_database_reachable() -> Dict[str, Any]:
    reachable = bool(test_db_connection())
    if not reachable:
        degraded_state = _load_startup_degraded_state()
        if degraded_state.get("degraded"):
            return _build_check(
                "database_reachable",
                "warning",
                "Database connection test failed, but the API started in degraded mode.",
                details={"degraded_startup": True, "startup_error": degraded_state.get("error", "")},
                next_action="Restore database connectivity and restart the API before production use.",
            )
        return _build_check(
            "database_reachable",
            "blocked",
            "Database connection test failed.",
            blocking=True,
            next_action="Verify the database is running and DATABASE_URL points to a reachable instance.",
        )
    return _build_check(
        "database_reachable",
        "ready",
        "Database connection test succeeded.",
    )


def _check_router_state() -> List[Dict[str, Any]]:
    from app.api.router_registry import LEGACY_ROUTER_SPECS, PRODUCTION_ROUTER_SPECS, iter_router_specs

    report = _load_router_report()
    loaded_names = {str(item.get("name") or "") for item in report.get("loaded", []) if isinstance(item, dict)}
    default_specs = tuple(iter_router_specs())
    production_names = {spec.name for spec in PRODUCTION_ROUTER_SPECS}
    missing_production = sorted(name for name in production_names if name not in loaded_names)
    legacy_names = {spec.name for spec in LEGACY_ROUTER_SPECS}
    loaded_legacy = sorted(name for name in legacy_names if name in loaded_names)
    duplicate_routes = list(report.get("duplicates") or [])

    production_check = (
        _build_check(
            "production_routers_loaded",
            "blocked",
            "Some production routers were not loaded.",
            blocking=True,
            details={"missing_production_router_names": missing_production, "loaded_router_count": len(loaded_names)},
            next_action="Resolve router import failures and ensure all production routers are included at startup.",
        )
        if missing_production
        else _build_check(
            "production_routers_loaded",
            "ready",
            "All production routers are loaded.",
            details={"loaded_router_count": len(loaded_names), "default_router_spec_count": len(default_specs)},
        )
    )

    legacy_disabled_check = (
        _build_check(
            "legacy_routers_disabled",
            "blocked",
            "Legacy routers are loaded in the current application state.",
            blocking=True,
            details={"loaded_legacy_router_names": loaded_legacy, "legacy_env_flag": os.getenv("LMCP_ENABLE_LEGACY_ROUTERS", "")},
            next_action="Disable LMCP_ENABLE_LEGACY_ROUTERS and restart the API.",
        )
        if loaded_legacy
        else _build_check(
            "legacy_routers_disabled",
            "ready",
            "Legacy routers are disabled.",
            details={"legacy_router_count": len(legacy_names)},
        )
    )

    duplicates_check = (
        _build_check(
            "no_duplicate_routes",
            "blocked",
            "Duplicate routes were detected in the application.",
            blocking=True,
            details={"duplicates": duplicate_routes},
            next_action="Remove or rename overlapping routes before go-live.",
        )
        if duplicate_routes
        else _build_check(
            "no_duplicate_routes",
            "ready",
            "No duplicate routes detected.",
        )
    )
    return [production_check, legacy_disabled_check, duplicates_check]


def _build_pipeline_fixture(root: Path, *, title: str, extra_text: str = "") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "notice.txt").write_text(
        (
            f"{title}\n"
            "Supply and delivery tender.\n"
            "No compulsory briefing.\n"
            "Mandatory returnable documents include SBD 4 and pricing schedule.\n"
            f"{extra_text}\n"
        ),
        encoding="utf-8",
    )
    (root / "SBD 4 declaration.txt").write_text("SBD 4 declaration of interest", encoding="utf-8")
    return root


def _check_tender_submission_pipeline_importable() -> Dict[str, Any]:
    try:
        module = importlib.import_module("app.services.tender_submission_pipeline")
        pipeline_cls = getattr(module, "TenderSubmissionPipeline")
        pipeline_cls()
    except Exception as exc:
        return _build_check(
            "tender_submission_pipeline_importable",
            "blocked",
            f"TenderSubmissionPipeline import failed: {exc}",
            blocking=True,
            next_action="Fix the tender submission pipeline import path and dependencies.",
        )
    return _build_check(
        "tender_submission_pipeline_importable",
        "ready",
        "TenderSubmissionPipeline is importable.",
    )


def _check_pipeline_dry_run() -> Dict[str, Any]:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_root = _build_pipeline_fixture(Path(temp_dir) / "smoke", title="Supply and delivery of office chairs")
            result = TenderSubmissionPipeline().run(
                tender_root=str(fixture_root),
                tender_id="GO-LIVE-SMOKE",
                instructions_text="Supply and delivery of office chairs. No compulsory briefing.",
                mandatory_form_codes=["sbd4", "pricing_schedule"],
                company_data={"company_name": "LMCP"},
                director_data={"director_name": "Operator"},
                tender_data={
                    "tender_number": "GO-LIVE-SMOKE",
                    "tender_title": "Supply and delivery of office chairs",
                    "client_name": "Demo Buyer",
                },
                human_approval_granted=True,
                dry_run=True,
            )
    except Exception as exc:
        return _build_check(
            "dry_run_pipeline_passes",
            "blocked",
            f"Tender submission dry-run failed: {exc}",
            blocking=True,
            next_action="Fix the canonical tender submission pipeline until the smoke dry-run completes successfully.",
        )

    if result.get("status") != "dry_run_ready":
        return _build_check(
            "dry_run_pipeline_passes",
            "blocked",
            "Tender submission dry-run did not reach dry_run_ready.",
            blocking=True,
            details={"result_status": result.get("status"), "message": result.get("message")},
            next_action="Review the dry-run output and resolve the reported pipeline issue.",
        )
    return _build_check(
        "dry_run_pipeline_passes",
        "ready",
        "Tender submission dry-run passed.",
        details={"result_status": result.get("status")},
    )


def _check_human_approval_gate_enabled() -> Dict[str, Any]:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_root = _build_pipeline_fixture(Path(temp_dir) / "approval-gate", title="Supply and delivery of office stationery")
            result = TenderSubmissionPipeline().run(
                tender_root=str(fixture_root),
                tender_id="GO-LIVE-APPROVAL",
                instructions_text="Supply and delivery of office stationery. No compulsory briefing.",
                mandatory_form_codes=["sbd4"],
                tender_data={
                    "tender_number": "GO-LIVE-APPROVAL",
                    "tender_title": "Supply and delivery of office stationery",
                    "client_name": "Demo Buyer",
                },
                dry_run=True,
            )
    except Exception as exc:
        return _build_check(
            "human_approval_gate_enabled",
            "blocked",
            f"Human approval gate check failed: {exc}",
            blocking=True,
            next_action="Repair the assisted-production approval gate path in the tender submission pipeline.",
        )

    if result.get("status") != "pending_human_approval" or not result.get("human_approval_required"):
        return _build_check(
            "human_approval_gate_enabled",
            "blocked",
            "Human approval gate is not enforced by default.",
            blocking=True,
            details={"result_status": result.get("status"), "human_approval_required": result.get("human_approval_required")},
            next_action="Restore assisted_production mode so final submission always requires human approval.",
        )
    return _build_check(
        "human_approval_gate_enabled",
        "ready",
        "Human approval gate is enabled by default.",
    )


def _check_excluded_categories_enforced() -> Dict[str, Any]:
    blocked_codes: List[str] = []
    expected = {
        "medical consumables": "excluded_medical_consumables",
        "IT equipment": "excluded_it_equipment",
        "petrol and diesel": "excluded_petrol_diesel",
        "catering": "excluded_catering",
        "office stationery with compulsory briefing": "briefing_required",
    }
    try:
        for label, expected_code in expected.items():
            with tempfile.TemporaryDirectory() as temp_dir:
                extra = "Compulsory briefing session is required before submission." if expected_code == "briefing_required" else ""
                fixture_root = _build_pipeline_fixture(
                    Path(temp_dir) / "blocked",
                    title=f"Supply and delivery of {label}",
                    extra_text=extra,
                )
                result = TenderSubmissionPipeline().run(
                    tender_root=str(fixture_root),
                    tender_id=f"GO-LIVE-{expected_code}",
                    instructions_text=f"Supply and delivery of {label}. {extra}".strip(),
                    mandatory_form_codes=["sbd4"],
                    tender_data={
                        "tender_number": f"GO-LIVE-{expected_code}",
                        "tender_title": f"Supply and delivery of {label}",
                        "client_name": "Demo Buyer",
                    },
                    dry_run=True,
                )
                reason_codes = list((result.get("classification") or {}).get("reason_codes") or [])
                if result.get("status") == "blocked" and expected_code in reason_codes:
                    blocked_codes.append(expected_code)
    except Exception as exc:
        return _build_check(
            "excluded_categories_enforced",
            "blocked",
            f"Excluded category enforcement check failed: {exc}",
            blocking=True,
            next_action="Repair the tender exclusion rules in the canonical pipeline.",
        )

    missing = sorted(code for code in expected.values() if code not in blocked_codes)
    if missing:
        return _build_check(
            "excluded_categories_enforced",
            "blocked",
            "One or more excluded tender categories were not blocked.",
            blocking=True,
            details={"validated": blocked_codes, "missing": missing},
            next_action="Restore exclusion enforcement for all blocked tender categories.",
        )
    return _build_check(
        "excluded_categories_enforced",
        "ready",
        "Excluded tender categories are enforced.",
        details={"validated": blocked_codes},
    )


def _rollup_readiness(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    blocking_issues = [check["summary"] for check in checks if check.get("blocking")]
    recommended_next_actions = []
    for check in checks:
        next_action = str(check.get("next_action") or "").strip()
        if next_action:
            recommended_next_actions.append(next_action)
    if blocking_issues:
        overall_status = "blocked"
    elif any(check.get("status") == "warning" for check in checks):
        overall_status = "warning"
    else:
        overall_status = "ready"
    return {
        "overall_status": overall_status,
        "blocking_issues": blocking_issues,
        "recommended_next_actions": recommended_next_actions,
    }


def get_operator_dashboard_status_summary(readiness: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    readiness_payload = readiness or get_production_readiness()
    checks = list(readiness_payload.get("checks") or [])
    summary = get_guard_summary(limit=20).get("summary", {})
    return {
        "overall_status": readiness_payload.get("overall_status", "blocked"),
        "ready_checks": sum(1 for check in checks if check.get("status") == "ready"),
        "warning_checks": sum(1 for check in checks if check.get("status") == "warning"),
        "blocked_checks": sum(1 for check in checks if check.get("status") == "blocked"),
        "submission_locks": int(summary.get("submission_locks", 0) or 0),
        "operator_rejections": int(summary.get("operator_rejections", 0) or 0),
        "paused_sources": int(summary.get("paused_sources", 0) or 0),
        "go_live_readiness_url": "/go-live/readiness",
        "guard_summary_url": "/go-live-guards/summary",
        "updated_at": _now_iso(),
    }


def get_production_readiness() -> Dict[str, Any]:
    checks = [
        _check_database_reachable(),
        *_check_router_state(),
        _check_tender_submission_pipeline_importable(),
        _check_pipeline_dry_run(),
        _check_human_approval_gate_enabled(),
        _check_excluded_categories_enforced(),
        _check_required_env_vars(),
        _check_storage_writable(),
    ]
    rolled = _rollup_readiness(checks)
    readiness = {
        "status": "ok",
        "overall_status": rolled["overall_status"],
        "checks": checks,
        "blocking_issues": rolled["blocking_issues"],
        "recommended_next_actions": rolled["recommended_next_actions"],
        "checked_at": _now_iso(),
    }
    readiness["operator_dashboard_status_summary"] = get_operator_dashboard_status_summary(readiness)
    return readiness
