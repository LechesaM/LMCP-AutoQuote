from __future__ import annotations

from typing import Any, Dict, List

from ._shared import now_iso
from .policy_registry import build_policy_catalog


def build_policy_version_history() -> Dict[str, Any]:
    catalog = build_policy_catalog()
    history: List[Dict[str, Any]] = []
    for policy in catalog:
        history.append(
            {
                "policy_key": policy["policy_key"],
                "title": policy["title"],
                "version": policy["version"],
                "status": policy["status"],
                "effective_at": policy["effective_at"],
                "superseded_by": policy["superseded_by"],
                "approval_metadata": policy["approval_metadata"],
            }
        )
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "policy_versions": history,
        "superseded_policies": [],
        "effective_versions": len(history),
    }

