from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.core.runtime_paths import get_runtime_paths


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def governance_root() -> Path:
    root = get_runtime_paths().manual_production_dir / "governance"
    root.mkdir(parents=True, exist_ok=True)
    return root


def governance_path(filename: str) -> Path:
    path = governance_root() / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if payload is not None else default
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def append_jsonl(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    return payload


def safe_list(values: Iterable[Any] | None) -> list[Any]:
    return list(values or [])


def digest_json(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

