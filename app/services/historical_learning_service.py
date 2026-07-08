from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.pricing_outcome_calibration_service import PricingOutcomeCalibrationService
from app.services.procurement_intelligence_service import ProcurementIntelligenceService
from app.services.supplier_intelligence_service import SupplierIntelligenceService
from app.services.supplier_performance_memory_service import SupplierPerformanceMemoryService
from app.services.tender_outcome_learning_service import TenderOutcomeLearningService
from app.services.win_loss_analytics_service import WinLossAnalyticsService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "historical-learning-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "historical_learning_history.json"


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


def _unique(values: List[str]) -> List[str]:
    seen: List[str] = []
    for value in values:
        text = _safe_str(value)
        if text and text not in seen:
            seen.append(text)
    return seen


class HistoricalLearningService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.procurement_service = ProcurementIntelligenceService(runtime_dir=self.runtime_dir)
        self.supplier_service = SupplierIntelligenceService(runtime_dir=self.runtime_dir)
        self.pricing_service = PricingOutcomeCalibrationService(runtime_dir=self.runtime_dir)
        self.tender_outcome_service = TenderOutcomeLearningService(runtime_dir=self.runtime_dir)
        self.supplier_memory_service = SupplierPerformanceMemoryService(runtime_dir=self.runtime_dir)
        self.win_loss_service = WinLossAnalyticsService(runtime_dir=self.runtime_dir)

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
        procurement = self.procurement_service.latest_procurement_intelligence()
        supplier = self.supplier_service.latest_supplier_intelligence()
        pricing = self.pricing_service.latest_pricing_outcome_calibration()
        tender_outcome = self.tender_outcome_service.latest_tender_outcome_learning()
        supplier_memory = self.supplier_memory_service.latest_supplier_performance_memory()
        win_loss = self.win_loss_service.latest_win_loss_analytics()

        procurement_history = procurement.get("procurement_intelligence_history", [])
        supplier_outcomes = supplier.get("supplier_intelligence_history", [])
        pricing_outcomes = pricing.get("pricing_outcome_calibration_history", [])
        strategy_outcomes = tender_outcome.get("tender_strategy_outcomes", [])
        executive_outcomes = tender_outcome.get("executive_review_outcomes", [])
        boq_outcomes = pricing.get("boq_pricing_calibration_outcomes", [])
        supplier_performance_history = supplier_memory.get("supplier_performance_memory_history", [])
        win_loss_analytics_history = win_loss.get("win_loss_analytics_history", [])

        historical_learning_ready = bool(procurement.get("what_this_unlocks")) and bool(supplier.get("what_this_unlocks")) and bool(pricing.get("what_this_unlocks")) and bool(strategy_outcomes is not None) and bool(executive_outcomes is not None)
        tender_outcome_learning_ready = bool(tender_outcome.get("tender_outcome_learning_readiness", {}).get("ready"))
        supplier_memory_ready = bool(supplier_memory.get("supplier_memory_readiness", {}).get("ready"))
        pricing_calibration_ready = bool(pricing.get("pricing_calibration_readiness", {}).get("ready"))
        win_loss_ready = bool(win_loss.get("win_loss_analytics_readiness", {}).get("ready"))
        recommendation_feedback_ready = bool(tender_outcome.get("recommendation_feedback_readiness", {}).get("ready"))
        confidence_recalibration_ready = bool(pricing.get("confidence_recalibration_readiness", {}).get("ready"))
        historical_benchmark_ready = bool(tender_outcome.get("historical_benchmark_readiness", {}).get("ready")) or bool(pricing.get("historical_benchmark_readiness", {}).get("ready"))

        readiness_score = _clamp(
            mean(
                [
                    _safe_float(procurement.get("procurement_intelligence_score"), 0.0),
                    _safe_float(supplier.get("supplier_intelligence_score"), 0.0),
                    _safe_float(pricing.get("pricing_calibration_score"), 0.0),
                    _safe_float(tender_outcome.get("tender_outcome_learning_score"), 0.0),
                    _safe_float(supplier_memory.get("supplier_memory_score"), 0.0),
                    _safe_float(win_loss.get("win_loss_analytics_score"), 0.0),
                    100.0 if recommendation_feedback_ready else 55.0,
                    100.0 if confidence_recalibration_ready else 55.0,
                    100.0 if historical_benchmark_ready else 55.0,
                ]
            )
        )
        blockers = _unique(
            list((pricing.get("unresolved_learning_blockers") or []))
            + list((tender_outcome.get("unresolved_learning_blockers") or []))
            + list((supplier_memory.get("unresolved_learning_blockers") or []))
            + list((win_loss.get("unresolved_learning_blockers") or []))
        )
        ready = readiness_score >= 75.0 and not blockers
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        snapshot = {
            "analysis_id": f"historical-learning:{_safe_str(procurement.get('rfq_id') or procurement.get('analysis_id') or 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "historical_learning_status": status,
            "historical_learning_score": round(readiness_score, 2),
            "historical_learning_grade": "ready" if ready else "watch" if status == "watch" else "blocked",
            "historical_learning_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": blockers},
            "tender_outcome_learning_readiness": tender_outcome.get("tender_outcome_learning_readiness"),
            "supplier_memory_readiness": supplier_memory.get("supplier_memory_readiness"),
            "pricing_calibration_readiness": pricing.get("pricing_calibration_readiness"),
            "win_loss_analytics_readiness": win_loss.get("win_loss_analytics_readiness"),
            "recommendation_feedback_readiness": tender_outcome.get("recommendation_feedback_readiness"),
            "confidence_recalibration_readiness": pricing.get("confidence_recalibration_readiness"),
            "historical_benchmark_readiness": {
                "ready": historical_benchmark_ready,
                "status": "ok" if historical_benchmark_ready else "watch",
                "score": 100.0 if historical_benchmark_ready else 55.0,
                "blockers": [] if historical_benchmark_ready else ["historical benchmark evidence incomplete"],
            },
            "procurement_intelligence_history": procurement_history,
            "supplier_intelligence_outcomes": supplier_outcomes,
            "pricing_competitiveness_outcomes": pricing_outcomes,
            "tender_strategy_outcomes": strategy_outcomes,
            "executive_review_outcomes": executive_outcomes,
            "boq_pricing_calibration_outcomes": boq_outcomes,
            "supplier_performance_history": supplier_performance_history,
            "win_loss_analytics": win_loss,
            "win_loss_analytics_history": win_loss_analytics_history,
            "unresolved_learning_blockers": blockers,
            "autonomous_learning_execution_enabled": False,
            "autonomous_procurement_decision_updates_enabled": False,
            "autonomous_supplier_blacklisting_enabled": False,
            "autonomous_strategy_modification_enabled": False,
            "production_learning_mode_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_learning_review_required": True,
            "executive_feedback_required": True,
            "learning_governance_history": [
                {"event": "historical_learning_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "outcome_memory_reconciled", "status": "passed" if historical_learning_ready else "watch", "timestamp": _now_iso()},
            ],
            "what_this_unlocks": [
                "historical procurement learning",
                "supplier performance memory",
                "pricing calibration",
                "win/loss analytics",
                "supervised recommendation feedback",
            ],
            "warnings": [
                "Historical learning is advisory only" if not ready else "",
                "Production learning mode remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_historical_learning(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": snapshot["analysis_id"],
                    "generated_at": snapshot["generated_at"],
                    "historical_learning_status": snapshot["historical_learning_status"],
                    "historical_learning_score": snapshot["historical_learning_score"],
                }
            )
            self._write_history(history)
        return snapshot

    def latest_historical_learning(self) -> Dict[str, Any]:
        snapshot = self.analyze_historical_learning(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_historical_learning"] = dict(snapshot)
        payload["historical_learning_history"] = history
        payload["historical_learning_history_summary"] = {
            "analysis_count": len(history),
            "latest_score": snapshot["historical_learning_score"],
            "latest_status": snapshot["historical_learning_status"],
        }
        return payload

    def historical_learning_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("historical_learning_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "historical_learning_history": history,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_learning_review_required": True,
            "executive_feedback_required": True,
            "autonomous_learning_execution_enabled": False,
            "autonomous_procurement_decision_updates_enabled": False,
            "autonomous_supplier_blacklisting_enabled": False,
            "autonomous_strategy_modification_enabled": False,
            "production_learning_mode_enabled": False,
            "warnings": latest.get("warnings", []) if history else [],
        }
