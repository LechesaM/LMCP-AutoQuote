from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.tender_classification_service import TenderClassificationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "tender-strategy-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "tender_win_probability_history.json"


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


class TenderWinProbabilityService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = TenderClassificationService(runtime_dir=self.runtime_dir)

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

    def _sample_tender(self) -> Dict[str, Any]:
        return {
            "rfq_id": "win-probability:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "submission_method": "portal",
            "closing_date": _now_iso(),
            "unit_price": 118.0,
            "quantity": 20,
            "unit": "Each",
        }

    def _latest_tender(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_tender()

    def _estimate(self, tender: Dict[str, Any], bid_no_bid: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        classification = self.classification_service.analyze_tender(tender, record_history=False)
        bid_no_bid = bid_no_bid or {}
        complexity = _safe_float((classification.get("tender_complexity") or {}).get("score"), 0.0)
        urgency = _safe_float((classification.get("submission_urgency") or {}).get("score"), 0.0)
        document_count = len(classification.get("mandatory_documents") or [])
        base = mean([
            100.0 if classification.get("supply_tender") else 70.0,
            100.0 - min(complexity, 80.0),
            urgency,
            100.0 if document_count <= 8 else 75.0,
        ])
        if bid_no_bid.get("bid_no_bid_readiness", {}).get("ready"):
            base += 5.0
        win_probability = _clamp(base)
        risk_adjustment = _clamp(100.0 - win_probability)
        return {
            "analysis_id": f"tender-win-probability:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "win_probability_estimate": round(win_probability, 2),
            "win_probability_status": "high" if win_probability >= 70.0 else "medium" if win_probability >= 50.0 else "low",
            "win_probability_readiness": {
                "ready": win_probability >= 60.0,
                "score": round(win_probability, 2),
            },
            "risk_adjusted_opportunity_score": round(_clamp(mean([win_probability, 100.0 - complexity, urgency]) - min(risk_adjustment * 0.2, 20.0)), 2),
            "strategic_fit_score": round(_clamp(mean([100.0 if classification.get("supply_tender") else 70.0, 100.0 - min(complexity, 80.0), urgency])), 2),
            "submission_urgency_indicators": classification.get("submission_urgency") or {},
            "mandatory_document_readiness": {
                "ready": bool(classification.get("mandatory_documents")),
                "document_count": document_count,
            },
            "recommendation_degradation_indicators": {
                "complexity_drag": complexity >= 60.0,
                "insufficient_documents": document_count < 4,
            },
            "unresolved_strategy_blockers": [
                "win_probability_below_threshold" if win_probability < 50.0 else "",
            ],
            "warnings": [
                "Win probability requires human review" if win_probability < 70.0 else "",
            ],
        }

    def estimate_win_probability(self, tender: Dict[str, Any], bid_no_bid: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        analysis = self._estimate(tender, bid_no_bid=bid_no_bid)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "win_probability_estimate": analysis["win_probability_estimate"],
                    "strategic_fit_score": analysis["strategic_fit_score"],
                    "risk_adjusted_opportunity_score": analysis["risk_adjusted_opportunity_score"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_tender_win_probability(self) -> Dict[str, Any]:
        analysis = self.estimate_win_probability(self._latest_tender(), record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["win_probability_readiness"]["ready"] else "watch",
            "win_probability_status": analysis["win_probability_status"],
            "win_probability_estimate": analysis["win_probability_estimate"],
            "latest_tender_win_probability": analysis,
            "tender_win_probability_history": history,
            "tender_win_probability_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": analysis["analysis_id"],
            },
            "warnings": analysis["warnings"],
        }

    def tender_win_probability_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("win_probability_estimate"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "win_probability_status": "high" if score >= 70 else "medium" if score >= 50 else ("low" if history else "not_found"),
            "win_probability_estimate": score,
            "latest_tender_win_probability": latest,
            "tender_win_probability_history": history,
            "tender_win_probability_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": latest.get("analysis_id", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


tender_win_probability_service = TenderWinProbabilityService()
