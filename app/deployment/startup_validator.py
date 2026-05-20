from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from app.api.router_registry import iter_router_specs
from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now
from app.monitoring.reporting_service import build_operational_report
from app.monitoring.health_service import get_system_health
from app.monitoring.workflow_monitor import get_workflow_summary
from app.persistence import db
from app.persistence.repositories import get_persistence_health
from app.persistence.repositories import ApprovalRepository, AuditRepository, PricingRepository, QuoteRepository, SubmissionRepository, WorkflowRepository


class StartupValidationIssue(StrictBaseModel):
    level: str = "warning"
    code: str = ""
    message: str = ""


class StartupValidationReport(StrictBaseModel):
    status: str = "healthy"
    healthy: bool = True
    degraded: bool = False
    valid: bool = True
    checked_at: Any = None
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    fatal_issues: List[Dict[str, Any]] = Field(default_factory=list)
    warning_issues: List[Dict[str, Any]] = Field(default_factory=list)
    runtime_paths: Dict[str, Any] = Field(default_factory=dict)
    router_report: Dict[str, Any] = Field(default_factory=dict)


def _issue(level: str, code: str, message: str) -> Dict[str, Any]:
    return StartupValidationIssue(level=level, code=code, message=message).to_jsonable_dict()


def _load_production_router_signatures() -> Dict[str, Any]:
    duplicates: List[str] = []
    loaded: List[Dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_modules: set[str] = set()
    for spec in iter_router_specs():
        if spec.status != "production":
            continue
        loaded.append({"name": spec.name, "module": spec.module_path, "prefix": getattr(spec, "prefix", "") or ""})
        if spec.name in seen_names:
            duplicates.append(f"duplicate router name: {spec.name}")
        if spec.module_path in seen_modules:
            duplicates.append(f"duplicate router module: {spec.module_path}")
        seen_names.add(spec.name)
        seen_modules.add(spec.module_path)
    return {"loaded": loaded, "duplicates": duplicates}


def validate_startup(
    *,
    paths: Optional[RuntimePaths] = None,
    allow_degraded_startup: bool = False,
) -> Dict[str, Any]:
    runtime_paths = paths or get_runtime_paths()
    issues: List[Dict[str, Any]] = []

    for directory in runtime_paths.required_directories():
        if not directory.exists():
            issues.append(_issue("fatal", "missing_directory", f"Missing required directory: {directory}"))
        elif not directory.is_dir():
            issues.append(_issue("fatal", "invalid_directory", f"Not a directory: {directory}"))

    if not runtime_paths.manual_production_db_path.parent.exists():
        issues.append(_issue("fatal", "db_parent_missing", "SQLite database directory is missing"))
    if not db.safe_initialize_database():
        issues.append(_issue("fatal", "db_unavailable", "SQLite database could not be initialized"))
    elif not db.get_database_path().exists():
        issues.append(_issue("fatal", "db_missing", "SQLite database file is missing"))

    jsonl_targets = [
        runtime_paths.manual_production_file("workflow_events.jsonl"),
        runtime_paths.manual_production_file("workflow_state.jsonl"),
        runtime_paths.manual_production_file("approvals.jsonl"),
        runtime_paths.manual_production_file("submission_reviews.jsonl"),
        runtime_paths.manual_production_file("submission_proofs.jsonl"),
    ]
    for path in jsonl_targets:
        parent = path.parent
        if not parent.exists():
            issues.append(_issue("fatal", "jsonl_parent_missing", f"JSONL parent missing for {path.name}"))
        elif not parent.is_dir():
            issues.append(_issue("fatal", "jsonl_parent_invalid", f"JSONL parent invalid for {path.name}"))

    try:
        workflow_state_engine.get_current_state("startup-validation-probe")
    except Exception as exc:
        issues.append(_issue("fatal", "workflow_engine_unavailable", f"Workflow engine unavailable: {exc}"))

    for repo_name, repo in {
        "workflow": WorkflowRepository(jsonl_path=runtime_paths.manual_production_file("workflow_state.jsonl")),
        "approval": ApprovalRepository(),
        "submission": SubmissionRepository(),
        "audit": AuditRepository(),
        "pricing": PricingRepository(),
        "quote": QuoteRepository(),
    }.items():
        try:
            repo.fetch_recent(limit=1)
        except Exception as exc:
            issues.append(_issue("fatal", f"{repo_name}_repository_unavailable", str(exc)))

    try:
        system_health = get_system_health()
        if system_health.get("status") not in {"healthy", "warning"}:
            issues.append(_issue("warning", "system_health_degraded", str(system_health.get("message", "System health check reported a degraded state."))))
        persistence_health = get_persistence_health()
        if persistence_health.get("status") not in {"healthy", "warning"}:
            issues.append(_issue("warning", "persistence_health_degraded", str(persistence_health.get("message", "Persistence health check reported a degraded state."))))
    except Exception as exc:
        issues.append(_issue("fatal", "dashboard_unavailable", str(exc)))

    try:
        get_workflow_summary(limit=1)
    except Exception as exc:
        issues.append(_issue("fatal", "monitoring_unavailable", str(exc)))

    try:
        build_operational_report(limit=1)
    except Exception as exc:
        issues.append(_issue("warning", "operational_report_unavailable", str(exc)))

    router_report = _load_production_router_signatures()
    if router_report["duplicates"]:
        issues.append(_issue("fatal", "duplicate_production_routes", ", ".join(router_report["duplicates"])))

    fatal = [item for item in issues if item.get("level") == "fatal"]
    warnings = [item for item in issues if item.get("level") == "warning"]
    if fatal:
        status = "degraded" if allow_degraded_startup else "unhealthy"
    elif warnings:
        status = "degraded"
    else:
        status = "healthy"

    return StartupValidationReport(
        status=status,
        healthy=not fatal,
        degraded=bool(fatal or warnings),
        valid=not fatal,
        checked_at=utc_now(),
        issues=issues,
        fatal_issues=fatal,
        warning_issues=warnings,
        runtime_paths={
            "runtime_root": str(runtime_paths.runtime_root),
            "manual_production_dir": str(runtime_paths.manual_production_dir),
            "backups_dir": str(runtime_paths.backups_dir),
            "health_dir": str(runtime_paths.health_dir),
        },
        router_report=router_report,
    ).to_jsonable_dict()


def generate_startup_report(*, paths: Optional[RuntimePaths] = None, allow_degraded_startup: bool = False) -> Dict[str, Any]:
    return validate_startup(paths=paths, allow_degraded_startup=allow_degraded_startup)
