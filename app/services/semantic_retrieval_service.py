from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.contextual_memory_service import ContextualMemoryService
from app.services.historical_learning_service import HistoricalLearningService
from app.services.similarity_analysis_service import SimilarityAnalysisService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "vector-intelligence-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "semantic_retrieval_history.json"


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


class SemanticRetrievalService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.historical_learning_service = HistoricalLearningService(runtime_dir=self.runtime_dir)
        self.contextual_memory_service = ContextualMemoryService(runtime_dir=self.runtime_dir)
        self.similarity_analysis_service = SimilarityAnalysisService(runtime_dir=self.runtime_dir)

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
        contextual = self.contextual_memory_service.latest_contextual_memory()
        similarity = self.similarity_analysis_service.latest_similarity_analysis()
        retrieval_confidence = _clamp(mean([
            100.0 if historical.get("historical_learning_readiness", {}).get("ready") else 55.0,
            100.0 if contextual.get("contextual_memory_readiness", {}).get("ready") else 55.0,
            100.0 if similarity.get("similarity_analysis_readiness", {}).get("ready") else 55.0,
        ]))
        retrieval_ready = retrieval_confidence >= 70.0
        status = "ok" if retrieval_ready else "watch" if retrieval_confidence >= 55.0 else "blocked"
        blockers = [] if retrieval_ready else ["semantic retrieval coverage incomplete"]
        snapshot = {
            "analysis_id": f"semantic-retrieval:{_safe_str(historical.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": retrieval_ready,
            "status": status,
            "score": round(retrieval_confidence, 2),
            "blockers": blockers,
            "authority": "GO" if retrieval_ready else "WATCH" if status == "watch" else "NO_GO",
            "semantic_retrieval_status": status,
            "semantic_retrieval_score": round(retrieval_confidence, 2),
            "semantic_retrieval_readiness": {"ready": retrieval_ready, "status": status, "score": round(retrieval_confidence, 2), "blockers": blockers},
            "retrieval_confidence_indicators": {
                "historical_learning_ready": bool(historical.get("historical_learning_readiness", {}).get("ready")),
                "contextual_memory_ready": bool(contextual.get("contextual_memory_readiness", {}).get("ready")),
                "similarity_analysis_ready": bool(similarity.get("similarity_analysis_readiness", {}).get("ready")),
            },
            "semantic_clustering_readiness": {"ready": bool(similarity.get("semantic_clustering_readiness", {}).get("ready")), "status": similarity.get("semantic_clustering_readiness", {}).get("status", "watch"), "score": _safe_float((similarity.get("semantic_clustering_readiness") or {}).get("score"), 55.0), "blockers": list((similarity.get("semantic_clustering_readiness") or {}).get("blockers") or [])},
            "historical_retrieval_coverage": {
                "ready": bool(historical.get("historical_learning_readiness", {}).get("ready")),
                "count": len(historical.get("historical_learning_history", [])) + len(contextual.get("contextual_memory_history", [])),
            },
            "semantic_memory_lookup": {
                "historical_learning": historical.get("historical_learning_readiness"),
                "contextual_memory": contextual.get("contextual_memory_readiness"),
                "similarity_matches": similarity.get("similarity_matches", [])[:5],
            },
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
                {"event": "semantic_retrieval_ready", "status": "ready" if retrieval_ready else "blocked", "timestamp": _now_iso()},
                {"event": "similarity_lookup_completed", "status": "passed" if similarity.get("ready") else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Semantic retrieval is advisory only" if not retrieval_ready else "",
                "Production vector learning remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_semantic_retrieval(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "semantic_retrieval_status": snapshot["semantic_retrieval_status"], "semantic_retrieval_score": snapshot["semantic_retrieval_score"]})
            self._write_history(history)
        return snapshot

    def latest_semantic_retrieval(self) -> Dict[str, Any]:
        snapshot = self.analyze_semantic_retrieval(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_semantic_retrieval"] = dict(snapshot)
        payload["semantic_retrieval_history"] = history
        payload["semantic_retrieval_history_summary"] = {"analysis_count": len(history), "latest_score": snapshot["semantic_retrieval_score"], "latest_status": snapshot["semantic_retrieval_status"]}
        return payload

    def semantic_retrieval_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("semantic_retrieval_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "semantic_retrieval_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_retrieval_review_required": True, "embedding_governance_review_required": True, "autonomous_vector_decisioning_enabled": False, "autonomous_procurement_execution_enabled": False, "autonomous_supplier_selection_enabled": False, "autonomous_pricing_override_enabled": False, "production_vector_learning_enabled": False, "warnings": latest.get("warnings", []) if history else []}


semantic_retrieval_service = SemanticRetrievalService()
