from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def utcnow() -> datetime:
    return datetime.utcnow()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_source_name(source: Dict[str, Any]) -> str:
    return str(source.get("name") or source.get("url") or "unknown-source").strip()


def build_source_batches(
    sources: List[Dict[str, Any]],
    batch_size: int = 25,
) -> List[List[Dict[str, Any]]]:
    """
    Split sources into fixed-size batches.
    """
    if batch_size <= 0:
        batch_size = 25

    batches: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    for source in sources:
        current.append(source)
        if len(current) >= batch_size:
            batches.append(current)
            current = []

    if current:
        batches.append(current)

    return batches


def select_batch_for_cycle(
    sources: List[Dict[str, Any]],
    cycle_number: int,
    batch_size: int = 25,
) -> List[Dict[str, Any]]:
    """
    Round-robin batch selection based on cycle number.
    """
    if not sources:
        return []

    batches = build_source_batches(sources, batch_size=batch_size)
    if not batches:
        return []

    index = cycle_number % len(batches)
    return batches[index]


def apply_crawl_cap(
    sources: List[Dict[str, Any]],
    max_sources_per_cycle: int = 25,
) -> List[Dict[str, Any]]:
    """
    Hard cap on number of sources crawled in one cycle.
    """
    if max_sources_per_cycle <= 0:
        return sources
    return sources[:max_sources_per_cycle]


def get_next_cycle_number(state: Optional[Dict[str, Any]]) -> int:
    """
    Increments cycle counter from a persisted or in-memory state dict.
    """
    state = state or {}
    current = _safe_int(state.get("cycle_number", 0), 0)
    return current + 1


def update_cycle_state(
    state: Optional[Dict[str, Any]],
    *,
    selected_sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    state = dict(state or {})
    cycle_number = get_next_cycle_number(state)

    state["cycle_number"] = cycle_number
    state["last_cycle_at"] = utcnow().isoformat()
    state["last_selected_sources"] = [_normalize_source_name(s) for s in selected_sources]
    state["last_selected_count"] = len(selected_sources)
    return state


def summarize_batch_selection(
    *,
    total_sources: int,
    selected_sources: List[Dict[str, Any]],
    cycle_number: int,
    batch_size: int,
    max_sources_per_cycle: int,
) -> Dict[str, Any]:
    return {
        "cycle_number": cycle_number,
        "total_sources_available": total_sources,
        "selected_count": len(selected_sources),
        "batch_size": batch_size,
        "max_sources_per_cycle": max_sources_per_cycle,
        "selected_sources": [
            str(source.get("name") or source.get("url") or "unknown-source")
            for source in selected_sources
        ],
    }
