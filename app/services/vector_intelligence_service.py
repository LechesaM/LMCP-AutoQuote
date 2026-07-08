from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.contextual_memory_service import ContextualMemoryService
from app.services.embedding_governance_service import EmbeddingGovernanceService
from app.services.historical_learning_service import HistoricalLearningService
from app.services.semantic_retrieval_service import SemanticRetrievalService
from app.services.similarity_analysis_service import SimilarityAnalysisService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "vector-intelligence-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "vector_intelligence_history.json"


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


class VectorIntelligenceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.historical_learning_service = HistoricalLearningService(runtime_dir=self.runtime_dir)
        self.semantic_retrieval_service = SemanticRetrievalService(runtime_dir=self.runtime_dir)
        self.contextual_memory_service = ContextualMemoryService(runtime_dir=self.runtime_dir)
        self.similarity_analysis_service = SimilarityAnalysisService(runtime_dir=self.runtime_dir)
        self.embedding_governance_service = EmbeddingGovernanceService(runtime_dir=self.runtime_dir)

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
        retrieval = self.semantic_retrieval_service.latest_semantic_retrieval()
        contextual = self.contextual_memory_service.latest_contextual_memory()
        similarity = self.similarity_analysis_service.latest_similarity_analysis()
        embedding = self.embedding_governance_service.latest_embedding_governance()

        readiness_score = _clamp(mean([
            100.0 if historical.get("historical_learning_readiness", {}).get("ready") else 55.0,
            100.0 if retrieval.get("semantic_retrieval_readiness", {}).get("ready") else 55.0,
            100.0 if contextual.get("contextual_memory_readiness", {}).get("ready") else 55.0,
            100.0 if similarity.get("similarity_analysis_readiness", {}).get("ready") else 55.0,
            100.0 if embedding.get("embedding_governance_readiness", {}).get("ready") else 55.0,
        ]))
        ready = readiness_score >= 70.0
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        blockers = [] if ready else ["vector intelligence coverage incomplete"]
        snapshot = {
            "analysis_id": f"vector-intelligence:{_safe_str(historical.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "vector_intelligence_status": status,
            "vector_intelligence_score": round(readiness_score, 2),
            "vector_intelligence_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": blockers},
            "historical_learning_readiness": historical.get("historical_learning_readiness"),
            "semantic_retrieval_readiness": retrieval.get("semantic_retrieval_readiness"),
            "contextual_memory_readiness": contextual.get("contextual_memory_readiness"),
            "similarity_analysis_readiness": similarity.get("similarity_analysis_readiness"),
            "embedding_governance_readiness": embedding.get("embedding_governance_readiness"),
            "retrieval_confidence_indicators": retrieval.get("retrieval_confidence_indicators"),
            "semantic_clustering_readiness": similarity.get("semantic_clustering_readiness"),
            "historical_retrieval_coverage": retrieval.get("historical_retrieval_coverage"),
            "procurement_intelligence_memory": historical.get("procurement_intelligence_history", []),
            "supplier_memory": historical.get("supplier_intelligence_outcomes", []),
            "pricing_benchmark_memory": historical.get("pricing_competitiveness_outcomes", []),
            "boq_semantic_memory": historical.get("boq_pricing_calibration_outcomes", []),
            "tender_strategy_memory": historical.get("tender_strategy_outcomes", []),
            "executive_review_memory": historical.get("executive_review_outcomes", []),
            "historical_outcome_retrieval": historical.get("win_loss_analytics_history", []),
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
                {"event": "vector_intelligence_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "semantic_retrieval_reconciled", "status": "passed" if retrieval.get("ready") else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Vector intelligence is advisory only" if not ready else "",
                "Production vector learning remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_vector_intelligence(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "vector_intelligence_status": snapshot["vector_intelligence_status"], "vector_intelligence_score": snapshot["vector_intelligence_score"]})
            self._write_history(history)
        return snapshot

    def latest_vector_intelligence(self) -> Dict[str, Any]:
        snapshot = self.analyze_vector_intelligence(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_vector_intelligence"] = dict(snapshot)
        payload["vector_intelligence_history"] = history
        payload["vector_intelligence_history_summary"] = {"analysis_count": len(history), "latest_score": snapshot["vector_intelligence_score"], "latest_status": snapshot["vector_intelligence_status"]}
        return payload

    def vector_intelligence_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("vector_intelligence_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "vector_intelligence_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_retrieval_review_required": True, "embedding_governance_review_required": True, "autonomous_vector_decisioning_enabled": False, "autonomous_procurement_execution_enabled": False, "autonomous_supplier_selection_enabled": False, "autonomous_pricing_override_enabled": False, "production_vector_learning_enabled": False, "warnings": latest.get("warnings", []) if history else []}


vector_intelligence_service = VectorIntelligenceService()
