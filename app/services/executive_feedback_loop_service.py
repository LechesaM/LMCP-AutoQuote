from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.recommendation_feedback_service import RecommendationFeedbackService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "recommendation-feedback-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "executive_feedback_loop_history.json"


class ExecutiveFeedbackLoopService:
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
        ready = bool(feedback.get("recommendation_feedback_readiness", {}).get("ready"))
        status = "ok" if ready else "watch"
        snapshot = {
            "analysis_id": f"executive-feedback-loop:{feedback.get('analysis_id', 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": 100.0 if ready else 55.0,
            "blockers": [] if ready else ["executive feedback loop coverage incomplete"],
            "authority": "GO" if ready else "WATCH",
            "executive_feedback_loop_status": status,
            "executive_feedback_loop_score": 100.0 if ready else 55.0,
            "executive_feedback_loop_readiness": {"ready": ready, "status": status, "score": 100.0 if ready else 55.0, "blockers": [] if ready else ["executive feedback loop coverage incomplete"]},
            "recommendation_feedback_readiness": feedback.get("recommendation_feedback_readiness"),
            "confidence_drift_indicators": feedback.get("confidence_drift_indicators"),
            "false_positive_negative_indicators": feedback.get("false_positive_negative_indicators"),
            "unresolved_feedback_blockers": [] if ready else ["executive feedback loop coverage incomplete"],
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
            "feedback_loop_governance_history": [
                {"event": "executive_feedback_loop_ready", "status": "ready" if ready else "watch", "timestamp": _now_iso()},
            ],
            "warnings": ["Executive feedback loop remains advisory only" if not ready else ""],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_executive_feedback_loop(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "executive_feedback_loop_status": snapshot["executive_feedback_loop_status"], "executive_feedback_loop_score": snapshot["executive_feedback_loop_score"]})
            self._write_history(history)
        return snapshot

    def latest_executive_feedback_loop(self) -> Dict[str, Any]:
        snapshot = self.analyze_executive_feedback_loop(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_executive_feedback_loop"] = dict(snapshot)
        payload["executive_feedback_loop_history"] = history
        return payload

    def executive_feedback_loop_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("executive_feedback_loop_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "executive_feedback_loop_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_calibration_review_required": True, "analyst_feedback_review_required": True, "executive_feedback_review_required": True, "autonomous_feedback_learning_enabled": False, "autonomous_procurement_decision_updates_enabled": False, "autonomous_supplier_ranking_updates_enabled": False, "autonomous_pricing_override_enabled": False, "autonomous_strategy_modification_enabled": False, "production_calibration_mode_enabled": False, "warnings": latest.get("warnings", []) if history else []}


executive_feedback_loop_service = ExecutiveFeedbackLoopService()
