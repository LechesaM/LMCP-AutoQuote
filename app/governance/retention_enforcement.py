from __future__ import annotations

from typing import Any, Dict, List

from app.persistence.retention_policy import get_retention_policy, run_retention_dry_run

from ._shared import now_iso
from .legal_hold_manager import get_legal_holds


def build_retention_enforcement_report(*, dry_run: bool = True, confirm: bool = False) -> Dict[str, Any]:
    policy = get_retention_policy()
    dry_run_result = run_retention_dry_run(dry_run=dry_run, confirm=confirm)
    holds = get_legal_holds()
    protected_categories = {str(hold.get("scope") or "").lower() for hold in holds.get("holds", []) if hold.get("active")}
    would_archive = [
        item
        for item in dry_run_result.get("would_delete", [])
        if str(item.get("category") or "").lower() not in protected_categories
    ]
    blocked = [
        item
        for item in dry_run_result.get("would_delete", [])
        if str(item.get("category") or "").lower() in protected_categories
    ]
    warnings: List[str] = []
    if blocked:
        warnings.append("One or more retention categories are protected by legal hold.")
    if not dry_run:
        warnings.append("Retention enforcement requires explicit confirmation before destructive action.")
    status = "healthy" if not blocked else "degraded"
    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime",
        "retention_policy": policy,
        "dry_run_result": dry_run_result,
        "legal_holds": holds,
        "would_archive": would_archive,
        "blocked_by_legal_hold": blocked,
        "warnings": warnings,
        "blockers": [],
        "dry_run_only": True,
        "requires_explicit_confirmation": True,
    }

