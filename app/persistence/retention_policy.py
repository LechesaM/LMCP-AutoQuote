from __future__ import annotations

from typing import Any, Dict


def run_retention_dry_run(*, dry_run: bool = True, confirm: bool = False) -> Dict[str, Any]:
    return {"dry_run": dry_run, "confirmed": confirm, "deleted": []}
