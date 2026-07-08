from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.contextual_memory_service import ContextualMemoryService
from app.services.historical_learning_service import HistoricalLearningService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "vector-intelligence-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "similarity_analysis_history.json"


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


def _tokens(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", text.lower()) if len(token) > 2}


class SimilarityAnalysisService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.historical_learning_service = HistoricalLearningService(runtime_dir=self.runtime_dir)
        self.contextual_memory_service = ContextualMemoryService(runtime_dir=self.runtime_dir)

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

    def _reference_blobs(self) -> List[Dict[str, Any]]:
        historical = self.historical_learning_service.latest_historical_learning()
        contextual = self.contextual_memory_service.latest_contextual_memory()
        blobs: List[Dict[str, Any]] = []
        for source_name, source in (
            ("procurement", historical.get("procurement_intelligence_history", [])),
            ("supplier", historical.get("supplier_intelligence_outcomes", [])),
            ("pricing", historical.get("pricing_competitiveness_outcomes", [])),
            ("boq", historical.get("boq_pricing_calibration_outcomes", [])),
            ("strategy", historical.get("tender_strategy_outcomes", [])),
            ("executive", historical.get("executive_review_outcomes", [])),
            ("outcome", historical.get("win_loss_analytics_history", [])),
            ("memory", contextual.get("contextual_memory_history", [])),
        ):
            if isinstance(source, list):
                for entry in source[:25]:
                    if isinstance(entry, dict):
                        text = " ".join(str(entry.get(field) or "") for field in entry.keys())
                        blobs.append({"source": source_name, "text": text[:2000], "entry": entry})
        return blobs

    def _build_snapshot(self) -> Dict[str, Any]:
        historical = self.historical_learning_service.latest_historical_learning()
        contextual = self.contextual_memory_service.latest_contextual_memory()
        reference_blobs = self._reference_blobs()
        query_blob = " ".join([
            _safe_str(historical.get("analysis_id")),
            _safe_str(historical.get("historical_learning_status")),
            _safe_str(contextual.get("contextual_memory_status")),
            "procurement supplier pricing boq strategy executive outcome memory",
        ])
        query_tokens = _tokens(query_blob)
        similarity_rows = []
        for blob in reference_blobs:
            blob_tokens = _tokens(blob["text"])
            if not blob_tokens:
                continue
            overlap = len(query_tokens & blob_tokens)
            union = len(query_tokens | blob_tokens) or 1
            score = (overlap / union) * 100.0
            similarity_rows.append({"source": blob["source"], "similarity_score": round(score, 2), "matched_terms": sorted(query_tokens & blob_tokens)[:12], "reference": blob["entry"]})
        similarity_rows.sort(key=lambda item: item["similarity_score"], reverse=True)
        top_similarity = similarity_rows[0]["similarity_score"] if similarity_rows else 0.0
        semantic_clustering_ready = bool(similarity_rows) and top_similarity >= 20.0
        ready = top_similarity >= 15.0 and bool(contextual.get("contextual_memory_readiness", {}).get("ready"))
        status = "ok" if ready else "watch" if top_similarity >= 10.0 else "blocked"
        blockers = [] if ready else ["semantic similarity coverage incomplete"]
        snapshot = {
            "analysis_id": f"similarity-analysis:{_safe_str(historical.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(top_similarity, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "similarity_analysis_status": status,
            "similarity_analysis_score": round(top_similarity, 2),
            "similarity_analysis_readiness": {"ready": ready, "status": status, "score": round(top_similarity, 2), "blockers": blockers},
            "semantic_clustering_readiness": {"ready": semantic_clustering_ready, "status": "ok" if semantic_clustering_ready else "watch", "score": 100.0 if semantic_clustering_ready else 55.0, "blockers": [] if semantic_clustering_ready else ["semantic clustering coverage incomplete"]},
            "retrieval_confidence_indicators": {"historical_learning_ready": bool(historical.get("historical_learning_readiness", {}).get("ready")), "contextual_memory_ready": bool(contextual.get("contextual_memory_readiness", {}).get("ready")), "reference_count": len(reference_blobs)},
            "historical_retrieval_coverage": {"ready": bool(reference_blobs), "count": len(reference_blobs)},
            "similarity_matches": similarity_rows[:10],
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
                {"event": "similarity_analysis_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "semantic_clustering_verified", "status": "passed" if semantic_clustering_ready else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Similarity analysis is advisory only" if not ready else "",
                "Production vector learning remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_similarity(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "similarity_analysis_status": snapshot["similarity_analysis_status"], "similarity_analysis_score": snapshot["similarity_analysis_score"]})
            self._write_history(history)
        return snapshot

    def latest_similarity_analysis(self) -> Dict[str, Any]:
        snapshot = self.analyze_similarity(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_similarity_analysis"] = dict(snapshot)
        payload["similarity_analysis_history"] = history
        payload["similarity_analysis_history_summary"] = {"analysis_count": len(history), "latest_score": snapshot["similarity_analysis_score"], "latest_status": snapshot["similarity_analysis_status"]}
        return payload

    def similarity_analysis_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("similarity_analysis_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "similarity_analysis_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_retrieval_review_required": True, "embedding_governance_review_required": True, "autonomous_vector_decisioning_enabled": False, "autonomous_procurement_execution_enabled": False, "autonomous_supplier_selection_enabled": False, "autonomous_pricing_override_enabled": False, "production_vector_learning_enabled": False, "warnings": latest.get("warnings", []) if history else []}


similarity_analysis_service = SimilarityAnalysisService()
