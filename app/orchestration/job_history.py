from __future__ import annotations

from typing import Any, Dict, List

_HISTORY: Dict[str, List[Dict[str, Any]]] = {}


def append(job_id: str, item: Dict[str, Any]) -> None:
    _HISTORY.setdefault(job_id, []).append(dict(item))


def get_job_history(job_id: str) -> List[Dict[str, Any]]:
    return list(_HISTORY.get(job_id, []))
