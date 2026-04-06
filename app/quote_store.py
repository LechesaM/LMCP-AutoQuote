from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUOTES_KEY = os.getenv("QUOTES_REDIS_KEY", "autoquote:quotes")  # hash: quote_id -> json


def _client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def save_quote(quote: Dict[str, Any]) -> str:
    quote_id = str(uuid.uuid4())
    r = _client()
    r.hset(QUOTES_KEY, quote_id, json.dumps(quote, ensure_ascii=False))
    return quote_id


def get_quote(quote_id: str) -> Optional[Dict[str, Any]]:
    r = _client()
    raw = r.hget(QUOTES_KEY, quote_id)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def list_quotes(limit: int = 50) -> List[Dict[str, Any]]:
    r = _client()
    all_items = r.hgetall(QUOTES_KEY)
    # newest-first best effort: no timestamp ordering in hash, so we sort by created_date if present
    quotes: List[Dict[str, Any]] = []
    for _, raw in all_items.items():
        try:
            quotes.append(json.loads(raw))
        except Exception:
            continue

    quotes.sort(key=lambda q: str(q.get("created_at", "")), reverse=True)
    return quotes[: max(1, int(limit))]
