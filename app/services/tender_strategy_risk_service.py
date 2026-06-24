from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.pricing_intelligence_governance_service import PricingIntelligenceGovernanceService
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.tender_classification_service import TenderClassificationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "tender-strategy-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "tender_strategy_risk_history.json"


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


class TenderStrategyRiskService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = TenderClassificationService(runtime_dir=self.runtime_dir)
        self.pricing_intelligence_service = PricingIntelligenceGovernanceService(runtime_dir=self.runtime_dir)

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
            "rfq_id": "strategy-risk:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "submission_method": "portal",
            "closing_date": _now_iso(),
            "unit_price": 118.0,
            "quantity": 20,
            "unit": "Each",
            "vat_rate": 0.15,
            "markup_rate": 0.25,
        }

    def _latest_tender(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_tender()

    def _assess(self, tender: Dict[str, Any], bid_no_bid: Optional[Dict[str, Any]] = None, win_probability: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        classification = self.classification_service.analyze_tender(tender, record_history=False)
        pricing = self.pricing_intelligence_service.latest_pricing_intelligence()
        bid_no_bid = bid_no_bid or {}
        win_probability = win_probability or {}

        complexity = _safe_float((classification.get("tender_complexity") or {}).get("score"), 0.0)
        urgency = _safe_float((classification.get("submission_urgency") or {}).get("score"), 0.0)
        pricing_confidence = _safe_float(pricing.get("pricing_confidence_score"), 0.0)
        document_count = len(classification.get("mandatory_documents") or [])
        probability = _safe_float(win_probability.get("win_probability_estimate"), 0.0)
        bid_ready = bool((bid_no_bid.get("bid_no_bid_readiness") or {}).get("ready"))

        risk_components = [
            complexity,
            100.0 - probability,
            100.0 - pricing_confidence,
            100.0 if document_count < 4 else 35.0,
            urgency,
        ]
        risk_score = _clamp(mean(risk_components))
        if risk_score >= 75:
            risk_level = "extreme"
        elif risk_score >= 60:
            risk_level = "high"
        elif risk_score >= 35:
            risk_level = "medium"
        else:
            risk_level = "low"

        risk_flags = []
        if complexity >= 60.0:
            risk_flags.append("high_tender_complexity")
        if probability < 50.0:
            risk_flags.append("low_win_probability")
        if pricing_confidence < 70.0:
            risk_flags.append("pricing_confidence_gap")
        if document_count < 4:
            risk_flags.append("mandatory_document_gap")

        unresolved_blockers = []
        if risk_level in {"high", "extreme"}:
            unresolved_blockers.append("executive_review_required")
        if not bid_ready:
            unresolved_blockers.append("bid_readiness_not_met")
        if pricing_confidence < 70.0:
            unresolved_blockers.append("pricing_readiness_incomplete")

        return {
            "analysis_id": f"strategy-risk:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "risk_flags": risk_flags,
            "strategic_fit_score": round(_clamp(mean([100.0 - complexity, probability, pricing_confidence])), 2),
            "pricing_competitiveness_alignment": round(pricing_confidence, 2),
            "supplier_readiness_alignment": round(probability, 2),
            "compliance_readiness_alignment": round(100.0 if document_count >= 5 else 55.0, 2),
            "risk_adjusted_opportunity_score": round(_clamp(mean([probability, 100.0 - risk_score, pricing_confidence])), 2),
            "executive_review_required": risk_level in {"high", "extreme"} or pricing_confidence < 70.0,
            "mandatory_document_readiness": {
                "ready": document_count >= 4,
                "document_count": document_count,
            },
            "submission_urgency_indicators": classification.get("submission_urgency") or {},
            "recommendation_degradation_indicators": {
                "complexity_degradation": complexity >= 60.0,
                "probability_degradation": probability < 50.0,
                "pricing_degradation": pricing_confidence < 70.0,
            },
            "unresolved_strategy_blockers": unresolved_blockers,
            "warnings": [
                "Strategy risk requires executive review" if risk_level in {"high", "extreme"} else "",
            ],
        }

    def assess_strategy_risk(self, tender: Dict[str, Any], bid_no_bid: Optional[Dict[str, Any]] = None, win_probability: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        analysis = self._assess(tender, bid_no_bid=bid_no_bid, win_probability=win_probability)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "risk_score": analysis["risk_score"],
                    "risk_level": analysis["risk_level"],
                    "strategic_fit_score": analysis["strategic_fit_score"],
                    "risk_adjusted_opportunity_score": analysis["risk_adjusted_opportunity_score"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_tender_strategy_risk(self) -> Dict[str, Any]:
        analysis = self.assess_strategy_risk(self._latest_tender(), record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["risk_level"] in {"low", "medium"} else "watch",
            "tender_strategy_risk_status": analysis["risk_level"],
            "tender_strategy_risk_score": analysis["risk_score"],
            "latest_tender_strategy_risk": analysis,
            "tender_strategy_risk_history": history,
            "tender_strategy_risk_history_summary": {
                "analysis_count": len(history),
                "latest_risk_level": analysis["risk_level"],
            },
            "warnings": analysis["warnings"],
        }

    def tender_strategy_risk_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("risk_score"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "tender_strategy_risk_status": "high" if score >= 60 else "medium" if score >= 35 else ("low" if history else "not_found"),
            "tender_strategy_risk_score": score,
            "latest_tender_strategy_risk": latest,
            "tender_strategy_risk_history": history,
            "tender_strategy_risk_history_summary": {
                "analysis_count": len(history),
                "latest_risk_level": latest.get("risk_level", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


tender_strategy_risk_service = TenderStrategyRiskService()
