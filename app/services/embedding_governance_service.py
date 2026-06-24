from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.historical_learning_service import HistoricalLearningService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "vector-intelligence-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "embedding_governance_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class EmbeddingGovernanceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.historical_learning_service = HistoricalLearningService(runtime_dir=self.runtime_dir)

    def _load_history(self) -> List[Dict[str, Any]]:
        path = _history_file(self.runtime_dir)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text())
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        path = _history_file(self.runtime_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history[-250:], indent=2, default=str))

    def _build_snapshot(self) -> Dict[str, Any]:
        historical = self.historical_learning_service.latest_historical_learning()
        historical_ready = bool(historical.get("historical_learning_readiness", {}).get("ready"))
        history_count = _safe_float(historical.get("count"), 0.0)
        embedding_score = _clamp(mean([
            100.0 if historical_ready else 55.0,
            100.0 if history_count > 0 else 55.0,
            100.0 if not historical.get("blockers") else 70.0,
        ]))
        ready = embedding_score >= 70.0
        status = "ok" if ready else "watch" if embedding_score >= 55.0 else "blocked"
        blockers = [] if ready else ["historical learning memory incomplete"]
        snapshot = {
            "analysis_id": f"embedding-governance:{_safe_str(historical.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(embedding_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "embedding_governance_status": status,
            "embedding_governance_score": round(embedding_score, 2),
            "embedding_governance_readiness": {"ready": ready, "status": status, "score": round(embedding_score, 2), "blockers": blockers},
            "retrieval_confidence_indicators": {
                "historical_learning_ready": historical_ready,
                "history_count": int(history_count),
                "semantic_memory_present": bool(historical.get("what_this_unlocks")),
            },
            "semantic_clustering_readiness": {"ready": ready, "status": status, "score": round(embedding_score, 2), "blockers": blockers},
            "historical_retrieval_coverage": {"ready": historical_ready, "score": 100.0 if historical_ready else 55.0},
            "unresolved_vector_blockers": blockers,
            "autonomous_vector_decisioning_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_supplier_selection_enabled": False,
            "autonomous_pricing_override_enabled": False,
            "production_vector_learning_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_retrieval_review_required": True,
            "embedding_governance_review_required": True,
            "vector_governance_history": [
                {"event": "embedding_governance_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "historical_learning_retrieved", "status": "passed" if historical_ready else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Vector intelligence remains advisory only" if not ready else "",
                "Production vector learning remains disabled",
            ],
            "historical_learning_latest": historical,
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_embedding_governance(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": snapshot["analysis_id"],
                    "generated_at": snapshot["generated_at"],
                    "embedding_governance_status": snapshot["embedding_governance_status"],
                    "embedding_governance_score": snapshot["embedding_governance_score"],
                }
            )
            self._write_history(history)
        return snapshot

    def latest_embedding_governance(self) -> Dict[str, Any]:
        snapshot = self.analyze_embedding_governance(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_embedding_governance"] = dict(snapshot)
        payload["embedding_governance_history"] = history
        payload["embedding_governance_history_summary"] = {
            "analysis_count": len(history),
            "latest_score": snapshot["embedding_governance_score"],
            "latest_status": snapshot["embedding_governance_status"],
        }
        return payload

    def embedding_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("embedding_governance_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "embedding_governance_history": history,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_retrieval_review_required": True,
            "embedding_governance_review_required": True,
            "autonomous_vector_decisioning_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_supplier_selection_enabled": False,
            "autonomous_pricing_override_enabled": False,
            "production_vector_learning_enabled": False,
            "warnings": latest.get("warnings", []) if history else [],
        }


embedding_governance_service = EmbeddingGovernanceService()
