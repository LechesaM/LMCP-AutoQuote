from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


STATE_DIR = Path(os.getenv("LMCP_STATE_DIR", "data"))
STATE_FILE = STATE_DIR / "crawl_cycle_state.json"


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_cycle_state() -> Dict[str, Any]:
    """
    Load persisted crawl cycle state from disk.
    """
    ensure_state_dir()

    if not STATE_FILE.exists():
        return {
            "cycle_number": 0,
            "last_cycle_at": None,
            "last_selected_sources": [],
            "last_selected_count": 0,
        }

    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {
                "cycle_number": 0,
                "last_cycle_at": None,
                "last_selected_sources": [],
                "last_selected_count": 0,
            }

        return data
    except Exception:
        return {
            "cycle_number": 0,
            "last_cycle_at": None,
            "last_selected_sources": [],
            "last_selected_count": 0,
        }


def save_cycle_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save crawl cycle state to disk.
    """
    ensure_state_dir()

    payload = dict(state or {})

    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return payload


def reset_cycle_state() -> Dict[str, Any]:
    """
    Reset the crawl cycle state back to defaults.
    """
    payload = {
        "cycle_number": 0,
        "last_cycle_at": None,
        "last_selected_sources": [],
        "last_selected_count": 0,
    }
    return save_cycle_state(payload)
