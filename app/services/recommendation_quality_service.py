from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.historical_learning_service import HistoricalLearningService
from app.services.vector_intelligence_service import VectorIntelligenceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "recommendation-feedback-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "recommendation_quality_history.json"


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


class RecommendationQualityService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.historical_learning_service = HistoricalLearningService(runtime_dir=self.runtime_dir)
        self.vector_intelligence_service = VectorIntelligenceService(runtime_dir=self.runtime_dir)

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
        vector = self.vector_intelligence_service.latest_vector_intelligence()
        readiness_score = _clamp(mean([
            100.0 if historical.get("historical_learning_readiness", {}).get("ready") else 55.0,
            100.0 if vector.get("vector_intelligence_readiness", {}).get("ready") else 55.0,
            100.0 if historical.get("historical_learning_history") else 55.0,
            100.0 if vector.get("vector_intelligence_history") else 55.0,
        ]))
        ready = readiness_score >= 70.0
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        blockers = [] if ready else ["recommendation quality coverage incomplete"]
        snapshot = {
            "analysis_id": f"recommendation-quality:{_safe_str(historical.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "recommendation_quality_status": status,
            "recommendation_quality_score": round(readiness_score, 2),
            "recommendation_quality_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": blockers},
            "historical_learning_readiness": historical.get("historical_learning_readiness"),
            "vector_intelligence_readiness": vector.get("vector_intelligence_readiness"),
            "feedback_coverage_indicators": {
                "historical_learning_ready": bool(historical.get("historical_learning_readiness", {}).get("ready")),
                "vector_intelligence_ready": bool(vector.get("vector_intelligence_readiness", {}).get("ready")),
                "history_depth": len(historical.get("historical_learning_history", [])) + len(vector.get("vector_intelligence_history", [])),
            },
            "confidence_drift_indicators": {"drift_pct": round(max(0.0, 100.0 - readiness_score) / 5.0, 2), "stable": readiness_score >= 80.0},
            "false_positive_negative_indicators": {"false_positive_rate": round(max(0.0, 60.0 - readiness_score) / 3.0, 2), "false_negative_rate": round(max(0.0, 65.0 - readiness_score) / 3.5, 2)},
            "unresolved_feedback_blockers": blockers,
            "autonomous_feedback_learning_enabled": False,
            "autonomous_procurement_decision_updates_enabled": False,
            "autonomous_supplier_ranking_updates_enabled": False,
            "autonomous_pricing_override_enabled": False,
            "autonomous_strategy_modification_enabled": False,
            "production_calibration_mode_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_calibration_review_required": True,
            "analyst_feedback_review_required": True,
            "executive_feedback_review_required": True,
            "recommendation_feedback_governance_history": [
                {"event": "recommendation_feedback_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "confidence_calibration_reconciled", "status": "passed" if vector.get("ready") else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Recommendation feedback remains advisory only" if not ready else "",
                "Production calibration mode remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_recommendation_quality(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "recommendation_quality_status": snapshot["recommendation_quality_status"], "recommendation_quality_score": snapshot["recommendation_quality_score"]})
            self._write_history(history)
        return snapshot

    def latest_recommendation_quality(self) -> Dict[str, Any]:
        snapshot = self.analyze_recommendation_quality(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_recommendation_quality"] = dict(snapshot)
        payload["recommendation_quality_history"] = history
        payload["recommendation_quality_history_summary"] = {"analysis_count": len(history), "latest_score": snapshot["recommendation_quality_score"], "latest_status": snapshot["recommendation_quality_status"]}
        return payload

    def recommendation_quality_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("recommendation_quality_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "recommendation_quality_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_calibration_review_required": True, "analyst_feedback_review_required": True, "executive_feedback_review_required": True, "autonomous_feedback_learning_enabled": False, "autonomous_procurement_decision_updates_enabled": False, "autonomous_supplier_ranking_updates_enabled": False, "autonomous_pricing_override_enabled": False, "autonomous_strategy_modification_enabled": False, "production_calibration_mode_enabled": False, "warnings": latest.get("warnings", []) if history else []}


recommendation_quality_service = RecommendationQualityService()
