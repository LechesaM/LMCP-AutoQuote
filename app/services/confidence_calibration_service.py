from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.recommendation_feedback_service import RecommendationFeedbackService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "recommendation-feedback-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "confidence_calibration_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class ConfidenceCalibrationService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.recommendation_feedback_service = RecommendationFeedbackService(runtime_dir=self.runtime_dir)

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
        feedback = self.recommendation_feedback_service.latest_recommendation_feedback()
        base_score = float(feedback.get("recommendation_feedback_score", 0.0))
        drift_pct = round(max(0.0, 100.0 - base_score) / 4.0, 2)
        calibrated_score = _clamp(mean([base_score, 100.0 - drift_pct, 100.0 if feedback.get("ready") else 55.0]))
        ready = calibrated_score >= 70.0
        status = "ok" if ready else "watch" if calibrated_score >= 55.0 else "blocked"
        blockers = [] if ready else ["confidence calibration coverage incomplete"]
        snapshot = {
            "analysis_id": f"confidence-calibration:{_safe_str(feedback.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(calibrated_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "confidence_calibration_status": status,
            "confidence_calibration_score": round(calibrated_score, 2),
            "confidence_calibration_readiness": {"ready": ready, "status": status, "score": round(calibrated_score, 2), "blockers": blockers},
            "recommendation_feedback_readiness": feedback.get("recommendation_feedback_readiness"),
            "analyst_feedback_review_readiness": feedback.get("analyst_feedback_review_readiness"),
            "executive_feedback_loop_readiness": feedback.get("executive_feedback_loop_readiness"),
            "confidence_drift_indicators": {"drift_pct": drift_pct, "stable": calibrated_score >= 80.0},
            "false_positive_negative_indicators": feedback.get("false_positive_negative_indicators"),
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
            "calibration_governance_history": [
                {"event": "confidence_calibration_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "feedback_quality_reconciled", "status": "passed" if feedback.get("ready") else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Confidence calibration remains advisory only" if not ready else "",
                "Production calibration mode remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_confidence_calibration(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "confidence_calibration_status": snapshot["confidence_calibration_status"], "confidence_calibration_score": snapshot["confidence_calibration_score"]})
            self._write_history(history)
        return snapshot

    def latest_confidence_calibration(self) -> Dict[str, Any]:
        snapshot = self.analyze_confidence_calibration(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_confidence_calibration"] = dict(snapshot)
        payload["confidence_calibration_history"] = history
        payload["confidence_calibration_history_summary"] = {"analysis_count": len(history), "latest_score": snapshot["confidence_calibration_score"], "latest_status": snapshot["confidence_calibration_status"]}
        return payload

    def confidence_calibration_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("confidence_calibration_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "confidence_calibration_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_calibration_review_required": True, "analyst_feedback_review_required": True, "executive_feedback_review_required": True, "autonomous_feedback_learning_enabled": False, "autonomous_procurement_decision_updates_enabled": False, "autonomous_supplier_ranking_updates_enabled": False, "autonomous_pricing_override_enabled": False, "autonomous_strategy_modification_enabled": False, "production_calibration_mode_enabled": False, "warnings": latest.get("warnings", []) if history else []}


confidence_calibration_service = ConfidenceCalibrationService()
