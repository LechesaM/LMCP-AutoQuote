from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.boq_semantic_understanding_service import BoqSemanticUnderstandingService
from app.services.pricing_intelligence_governance_service import PricingIntelligenceGovernanceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "historical-learning-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "pricing_outcome_calibration_history.json"


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


class PricingOutcomeCalibrationService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.pricing_service = PricingIntelligenceGovernanceService(runtime_dir=self.runtime_dir)
        self.boq_service = BoqSemanticUnderstandingService(runtime_dir=self.runtime_dir)

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

    def _sample_item(self) -> Dict[str, Any]:
        return {
            "rfq_id": "historical-learning-pricing:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "unit_price": 118.0,
            "quantity": 20,
            "unit": "Each",
            "vat_rate": 0.15,
            "markup_rate": 0.25,
            "boq_rows": [
                {"item_number": 1, "description": "A4 paper", "specification": "Ream of 500 sheets", "unit": "Ream", "quantity": 100},
            ],
        }

    def _build_snapshot(self) -> Dict[str, Any]:
        item = self._sample_item()
        pricing = self.pricing_service.analyze_pricing_intelligence(item, record_history=False)
        boq = self.boq_service.analyze_boq_semantics(item, record_history=False)
        pricing_history = self.pricing_service.pricing_intelligence_history(limit=8).get("pricing_intelligence_history", [])
        boq_history = self.boq_service.boq_semantic_understanding_history(limit=8).get("boq_semantic_understanding_history", [])

        pricing_score = _safe_float(pricing.get("pricing_intelligence_score"), 0.0)
        confidence_score = _safe_float(pricing.get("pricing_confidence_score"), 0.0)
        boq_score = _safe_float(boq.get("boq_semantic_understanding_score"), 0.0)
        calibration_score = _clamp(mean([pricing_score, confidence_score, boq_score, 100.0 if pricing_history else 55.0, 100.0 if boq_history else 55.0]))

        benchmark_ready = bool((pricing.get("pricing_benchmark_readiness") or {}).get("ready"))
        calibration_ready = calibration_score >= 75.0 and benchmark_ready
        confidence_recalibration_ready = confidence_score >= 70.0 and bool(pricing.get("mandatory_human_price_approval"))
        historical_benchmark_ready = bool(boq_history) or benchmark_ready
        blockers = _unique(
            list(pricing.get("unresolved_pricing_blockers") or [])
            + list(boq.get("unresolved_boq_semantic_blockers") or [])
        )
        ready = calibration_ready and not blockers
        status = "ok" if ready else "watch" if calibration_score >= 55.0 else "blocked"
        snapshot = {
            "analysis_id": f"pricing-outcome-calibration:{_safe_str(item.get('rfq_id') or item.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "rfq_id": _safe_str(item.get("rfq_id"), "n/a"),
            "title": _safe_str(item.get("title"), "n/a"),
            "ready": ready,
            "status": status,
            "score": round(calibration_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "pricing_calibration_status": status,
            "pricing_calibration_score": round(calibration_score, 2),
            "pricing_calibration_grade": "ready" if ready else "watch" if status == "watch" else "blocked",
            "pricing_calibration_readiness": {"ready": ready, "status": status, "score": round(calibration_score, 2), "blockers": blockers},
            "confidence_recalibration_readiness": {"ready": confidence_recalibration_ready, "status": "ok" if confidence_recalibration_ready else "watch", "score": 100.0 if confidence_recalibration_ready else 55.0, "blockers": [] if confidence_recalibration_ready else ["confidence recalibration requires supervision"]},
            "historical_benchmark_readiness": {"ready": historical_benchmark_ready, "status": "ok" if historical_benchmark_ready else "watch", "score": 100.0 if historical_benchmark_ready else 55.0, "blockers": [] if historical_benchmark_ready else ["historical pricing evidence incomplete"]},
            "pricing_competitiveness_outcomes": pricing_history,
            "boq_pricing_calibration_outcomes": boq_history,
            "pricing_intelligence_latest": pricing,
            "boq_semantic_latest": boq,
            "pricing_confidence_score": confidence_score,
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
                {"event": "pricing_calibration_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "confidence_recalibration_verified", "status": "passed" if confidence_recalibration_ready else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Pricing outcome calibration is advisory only" if not ready else "",
                "Confidence recalibration remains supervised" if not confidence_recalibration_ready else "",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def latest_pricing_outcome_calibration(self) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        history = self._load_history()
        history.append(
            {
                "analysis_id": snapshot["analysis_id"],
                "generated_at": snapshot["generated_at"],
                "rfq_id": snapshot["rfq_id"],
                "title": snapshot["title"],
                "pricing_calibration_status": snapshot["pricing_calibration_status"],
                "pricing_calibration_score": snapshot["pricing_calibration_score"],
                "pricing_confidence_score": snapshot["pricing_confidence_score"],
            }
        )
        self._write_history(history)
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_pricing_outcome_calibration"] = dict(snapshot)
        payload["pricing_outcome_calibration_history"] = history
        payload["pricing_outcome_calibration_history_summary"] = {
            "analysis_count": len(history),
            "latest_rfq_id": snapshot["rfq_id"],
            "latest_score": snapshot["pricing_calibration_score"],
        }
        return payload

    def list_pricing_outcome_calibration(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.latest_pricing_outcome_calibration()
        history = self._load_history()[-max(1, int(limit)) :]
        latest["count"] = len(history)
        latest["pricing_outcome_calibration_history"] = history
        latest["pricing_outcome_calibration_history_summary"] = {
            "analysis_count": len(history),
            "latest_rfq_id": latest["rfq_id"],
            "latest_score": latest["pricing_calibration_score"],
        }
        return latest

    def pricing_outcome_calibration_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("pricing_calibration_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "pricing_outcome_calibration_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
