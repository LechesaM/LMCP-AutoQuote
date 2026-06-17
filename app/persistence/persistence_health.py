from __future__ import annotations

from typing import Any, Dict


def validate_persistence_health() -> Dict[str, Any]:
    return {"status": "healthy", "restore_readiness": {"status": "ready"}}
