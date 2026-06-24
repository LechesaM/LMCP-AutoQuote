from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.historical_learning_service import HistoricalLearningService
from app.services.recommendation_quality_service import RecommendationQualityService
from app.services.vector_intelligence_service import VectorIntelligenceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "recommendation-feedback-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "recommendation_feedback_history.json"


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


class RecommendationFeedbackService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.historical_learning_service = HistoricalLearningService(runtime_dir=self.runtime_dir)
        self.vector_intelligence_service = VectorIntelligenceService(runtime_dir=self.runtime_dir)
        self.recommendation_quality_service = RecommendationQualityService(runtime_dir=self.runtime_dir)

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
        quality = self.recommendation_quality_service.latest_recommendation_quality()

        procurement_outcomes = historical.get("procurement_intelligence_history", [])
        supplier_outcomes = historical.get("supplier_intelligence_outcomes", [])
        pricing_outcomes = historical.get("pricing_competitiveness_outcomes", [])
        strategy_outcomes = historical.get("tender_strategy_outcomes", [])
        executive_outcomes = historical.get("executive_review_outcomes", [])
        analyst_feedback = quality.get("recommendation_quality_history", [])

        readiness_score = _clamp(mean([
            100.0 if historical.get("historical_learning_readiness", {}).get("ready") else 55.0,
            100.0 if vector.get("vector_intelligence_readiness", {}).get("ready") else 55.0,
            100.0 if quality.get("recommendation_quality_readiness", {}).get("ready") else 55.0,
            100.0 if procurement_outcomes else 55.0,
            100.0 if supplier_outcomes else 55.0,
            100.0 if pricing_outcomes else 55.0,
            100.0 if strategy_outcomes else 55.0,
            100.0 if executive_outcomes else 55.0,
        ]))
        ready = readiness_score >= 70.0
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        blockers = [] if ready else ["recommendation feedback coverage incomplete"]
        executive_loop_ready = bool(historical.get("historical_learning_readiness", {}).get("ready")) and bool(vector.get("vector_intelligence_readiness", {}).get("ready"))
        snapshot = {
            "analysis_id": f"recommendation-feedback:{_safe_str(historical.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "recommendation_feedback_status": status,
            "recommendation_feedback_score": round(readiness_score, 2),
            "recommendation_feedback_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": blockers},
            "confidence_calibration_readiness": quality.get("recommendation_quality_readiness"),
            "recommendation_quality_readiness": quality.get("recommendation_quality_readiness"),
            "analyst_feedback_review_readiness": {"ready": bool(analyst_feedback), "status": "ok" if analyst_feedback else "watch", "score": 100.0 if analyst_feedback else 55.0, "blockers": [] if analyst_feedback else ["analyst feedback history incomplete"]},
            "executive_feedback_loop_readiness": {"ready": executive_loop_ready, "status": "ok" if executive_loop_ready else "watch", "score": 100.0 if executive_loop_ready else 55.0, "blockers": [] if executive_loop_ready else ["executive feedback history incomplete"]},
            "feedback_coverage_indicators": {"procurement_outcomes": len(procurement_outcomes), "supplier_outcomes": len(supplier_outcomes), "pricing_outcomes": len(pricing_outcomes), "strategy_outcomes": len(strategy_outcomes), "executive_outcomes": len(executive_outcomes), "analyst_feedback": len(analyst_feedback)},
            "confidence_drift_indicators": quality.get("confidence_drift_indicators"),
            "false_positive_negative_indicators": quality.get("false_positive_negative_indicators"),
            "historical_learning_readiness": historical.get("historical_learning_readiness"),
            "vector_intelligence_readiness": vector.get("vector_intelligence_readiness"),
            "procurement_recommendation_outcomes": procurement_outcomes,
            "supplier_recommendation_outcomes": supplier_outcomes,
            "pricing_recommendation_outcomes": pricing_outcomes,
            "tender_strategy_recommendation_outcomes": strategy_outcomes,
            "executive_decision_feedback": executive_outcomes,
            "analyst_review_feedback": analyst_feedback,
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
                {"event": "confidence_calibration_reconciled", "status": "passed" if quality.get("ready") else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Recommendation feedback remains advisory only" if not ready else "",
                "Production calibration mode remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_recommendation_feedback(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "recommendation_feedback_status": snapshot["recommendation_feedback_status"], "recommendation_feedback_score": snapshot["recommendation_feedback_score"]})
            self._write_history(history)
        return snapshot

    def latest_recommendation_feedback(self) -> Dict[str, Any]:
        snapshot = self.analyze_recommendation_feedback(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_recommendation_feedback"] = dict(snapshot)
        payload["recommendation_feedback_history"] = history
        payload["recommendation_feedback_history_summary"] = {"analysis_count": len(history), "latest_score": snapshot["recommendation_feedback_score"], "latest_status": snapshot["recommendation_feedback_status"]}
        return payload

    def recommendation_feedback_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("recommendation_feedback_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "recommendation_feedback_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_calibration_review_required": True, "analyst_feedback_review_required": True, "executive_feedback_review_required": True, "autonomous_feedback_learning_enabled": False, "autonomous_procurement_decision_updates_enabled": False, "autonomous_supplier_ranking_updates_enabled": False, "autonomous_pricing_override_enabled": False, "autonomous_strategy_modification_enabled": False, "production_calibration_mode_enabled": False, "warnings": latest.get("warnings", []) if history else []}


recommendation_feedback_service = RecommendationFeedbackService()
