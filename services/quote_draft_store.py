from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", str(BASE_DIR / "runtime"))).expanduser().resolve()
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

QUOTE_DRAFT_FILE = RUNTIME_DIR / "quote_drafts.json"


class QuoteDraftStore:
    _lock = threading.Lock()

    @classmethod
    def _now_iso(cls) -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _empty_payload(cls) -> Dict[str, Any]:
        return {
            "updated_at": cls._now_iso(),
            "count": 0,
            "items": [],
        }

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        if not QUOTE_DRAFT_FILE.exists():
            return cls._empty_payload()

        try:
            with cls._lock:
                data = json.loads(QUOTE_DRAFT_FILE.read_text(encoding="utf-8"))

            if not isinstance(data, dict):
                return cls._empty_payload()

            items = data.get("items", [])
            if not isinstance(items, list):
                items = []

            return {
                "updated_at": data.get("updated_at") or cls._now_iso(),
                "count": len(items),
                "items": items,
            }
        except Exception:
            return cls._empty_payload()

    @classmethod
    def save_all(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload = {
            "updated_at": cls._now_iso(),
            "count": len(items),
            "items": items,
        }

        with cls._lock:
            QUOTE_DRAFT_FILE.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return payload

    @classmethod
    def replace_all(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return cls.save_all(items)

    @classmethod
    def append_many(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        current = cls.get_all()
        existing_items = current.get("items", [])
        combined = existing_items + items
        return cls.save_all(combined)
