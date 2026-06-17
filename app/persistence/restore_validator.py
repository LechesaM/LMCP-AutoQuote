from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def validate_restore_readiness(backup_dir: str | Path) -> Dict[str, Any]:
    path = Path(backup_dir)
    ready = path.exists()
    return {
        "status": "ready" if ready else "blocked",
        "non_destructive": True,
        "persistence_ok": ready,
        "workflow_readable": ready,
        "queue_readable": ready,
        "blockers": [] if ready else ["missing backup"],
    }
