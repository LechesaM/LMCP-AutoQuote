from __future__ import annotations

from typing import Any, Dict, List

from app.services.audit_trail_service import load_audit_events

from ._shared import now_iso
from .access_review_engine import build_access_review_report
from .audit_chain_validator import build_audit_chain_validation
from .policy_registry import build_policy_registry
from .retention_enforcement import build_retention_enforcement_report


def build_audit_export_package(limit: int = 500) -> Dict[str, Any]:
    events = load_audit_events()
    selected = events[-max(1, int(limit or 500)) :]
    csv_rows: List[Dict[str, Any]] = [
        {
            "id": item.get("id", ""),
            "event_type": item.get("event_type", ""),
            "source": item.get("source", ""),
            "severity": item.get("severity", ""),
            "buyer_rfq_number": item.get("buyer_rfq_number", ""),
            "quote_number": item.get("quote_number", ""),
            "created_at": item.get("created_at", ""),
        }
        for item in selected
    ]
    manifest = {
        "audit_events": len(selected),
        "policy_registry": len(build_policy_registry().get("policies", [])),
        "access_review_items": len(build_access_review_report().get("active_users", [])),
        "retention_categories": len(build_retention_enforcement_report().get("retention_policy", {}).get("windows_days", {})),
        "audit_integrity_score": build_audit_chain_validation().get("integrity_score", 0),
    }
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "manifest": manifest,
        "json_export": {
            "audit_events": selected,
            "retention": build_retention_enforcement_report(),
            "access_review": build_access_review_report(),
            "audit_integrity": build_audit_chain_validation(),
        },
        "csv_export": csv_rows,
        "zip_manifest": {
            "files": [
                {"name": "audit_events.json", "records": len(selected)},
                {"name": "audit_events.csv", "records": len(csv_rows)},
                {"name": "manifest.json", "records": 1},
            ]
        },
        "export_safe": True,
        "no_secrets": True,
    }

