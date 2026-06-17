from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict


_PERSISTENCE_HEALTH: Dict[str, Any] = {
    "status": "healthy",
    "read_successes": 0,
    "write_successes": 0,
    "write_failures": 0,
}


def reset_persistence_health() -> None:
    _PERSISTENCE_HEALTH.update({"status": "healthy", "read_successes": 0, "write_successes": 0, "write_failures": 0})


def get_persistence_health() -> Dict[str, Any]:
    return dict(_PERSISTENCE_HEALTH)


def record_persistence_write_success() -> None:
    _PERSISTENCE_HEALTH["write_successes"] = int(_PERSISTENCE_HEALTH.get("write_successes", 0)) + 1


def record_persistence_write_failure() -> None:
    _PERSISTENCE_HEALTH["write_failures"] = int(_PERSISTENCE_HEALTH.get("write_failures", 0)) + 1


@dataclass
class WorkflowRepository:
    jsonl_path: Path | None = None

    def append_state(self, record: Dict[str, Any]) -> Dict[str, Any]:
        path = self.jsonl_path
        if path is None:
            raise ValueError("jsonl_path is required")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
        return record

    def fetch_recent(self, limit: int = 50) -> list[Dict[str, Any]]:
        path = self.jsonl_path
        if path is None:
            return []
        path = Path(path)
        if not path.exists():
            return []
        records: list[Dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
        except Exception:
            return []
        if limit <= 0:
            return []
        return list(reversed(records[-limit:]))
