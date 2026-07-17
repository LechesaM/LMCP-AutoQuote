from __future__ import annotations

import logging
import os
from typing import Any, Dict

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


AUTO_HARVEST_ENABLED = _env_bool(
    "AUTO_HARVEST_ENABLED",
    default=False,
)


@celery_app.task(name="app.tasks.run_harvest_only")
def run_harvest_only(
    max_total: int = 20,
    max_per_source: int = 3,
    persist_to_live_store: bool = False,
    persist_source_health: bool = False,
) -> Dict[str, Any]:
    """
    Run harvesting only.

    Governance safeguards:
    - auto-quoting remains disabled;
    - autonomous downstream execution remains disabled;
    - no buyer submission is performed;
    - no supplier email is sent;
    - no Gmail send operation is invoked.

    The task may persist discovered RFQs to the canonical live store when
    persist_to_live_store=True.
    """
    if not AUTO_HARVEST_ENABLED:
        return {
            "status": "skipped",
            "task": "run_harvest_only",
            "reason": "AUTO_HARVEST_ENABLED is false",
            "persist_to_live_store": False,
            "persist_source_health": False,
            "auto_quote_enabled": False,
            "autonomous_downstream_enabled": False,
        }

    try:
        from app.services.harvest_entrypoint import run_canonical_harvest

        result = run_canonical_harvest(
            max_total=max_total,
            max_per_source=max_per_source,
            persist_to_live_store=persist_to_live_store,
            persist_source_health=persist_source_health,
        )

        result_status = ""

        if isinstance(result, dict):
            result_status = str(
                result.get("status") or ""
            ).strip().lower()

        if result_status in {
            "failed",
            "failure",
            "error",
        }:
            return {
                "status": "failed",
                "task": "run_harvest_only",
                "entrypoint": (
                    "app.services.harvest_entrypoint."
                    "run_canonical_harvest"
                ),
                "max_total": max_total,
                "max_per_source": max_per_source,
                "persist_to_live_store": persist_to_live_store,
                "persist_source_health": persist_source_health,
                "auto_quote_enabled": False,
                "autonomous_downstream_enabled": False,
                "result": result,
                "error": (
                    result.get("error")
                    or result.get("message")
                    or "Canonical harvesting reported failure"
                ),
            }

        return {
            "status": "ok",
            "task": "run_harvest_only",
            "entrypoint": (
                "app.services.harvest_entrypoint."
                "run_canonical_harvest"
            ),
            "max_total": max_total,
            "max_per_source": max_per_source,
            "persist_to_live_store": persist_to_live_store,
            "persist_source_health": persist_source_health,
            "auto_quote_enabled": False,
            "autonomous_downstream_enabled": False,
            "result": result,
        }

    except Exception as exc:
        logger.exception(
            "[HARVEST_TASK] run_harvest_only failed"
        )

        return {
            "status": "failed",
            "task": "run_harvest_only",
            "entrypoint": (
                "app.services.harvest_entrypoint."
                "run_canonical_harvest"
            ),
            "max_total": max_total,
            "max_per_source": max_per_source,
            "persist_to_live_store": False,
            "persist_source_health": False,
            "auto_quote_enabled": False,
            "autonomous_downstream_enabled": False,
            "error": str(exc),
        }


manual_harvest = run_harvest_only
