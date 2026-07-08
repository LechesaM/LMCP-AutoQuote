from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.risk_scoring_service import RiskScoringService
from app.services.tender_classification_service import TenderClassificationService
from app.services.tender_intelligence import buyer_score, classify_sector, detect_supply_tender, keyword_relevance_score


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "procurement-intelligence"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "opportunity_scoring_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _text_blob(tender: Dict[str, Any]) -> str:
    parts = [
        tender.get("title"),
        tender.get("description"),
        tender.get("raw_text"),
        tender.get("buyer_name"),
        tender.get("category"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


class OpportunityScoringService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = TenderClassificationService(runtime_dir=self.runtime_dir)
        self.risk_scoring_service = RiskScoringService(runtime_dir=self.runtime_dir)

    def _load_history(self) -> List[Dict[str, Any]]:
        history_path = _history_file(self.runtime_dir)
        if not history_path.exists():
            return []
        try:
            payload = json.loads(history_path.read_text())
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        history_path = _history_file(self.runtime_dir)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(json.dumps(history[-250:], indent=2, default=str))

    def _sample_tender(self) -> Dict[str, Any]:
        return {
            "rfq_id": "procurement-intelligence:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for supply and delivery of stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "submission_method": "portal",
            "closing_date": _now_iso(),
        }

    def _latest_tender(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=1).get("items", [])
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return first
        return self._sample_tender()

    def analyze_opportunity(
        self,
        tender: Dict[str, Any],
        classification: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
        record_history: bool = False,
    ) -> Dict[str, Any]:
        blob = _text_blob(tender)
        classification = classification or self.classification_service.analyze_tender(tender, record_history=False)
        risk = risk or self.risk_scoring_service.analyze_risk(tender, classification=classification, record_history=False)

        sector = _safe_str(classification.get("procurement_sector"), classify_sector(_safe_str(tender.get("title"), ""), _safe_str(tender.get("description"), "")))
        buyer_alignment = buyer_score(_safe_str(tender.get("buyer_name") or tender.get("buyer") or tender.get("organ_of_state"), "")) / 25.0 * 25.0
        keyword_alignment = min(keyword_relevance_score(_safe_str(tender.get("title"), ""), _safe_str(tender.get("description"), "")), 60.0)
        supply_alignment = 20.0 if detect_supply_tender(_safe_str(tender.get("title"), ""), _safe_str(tender.get("description"), "")) else 0.0
        sector_alignment = 15.0 if sector in {"water", "energy", "electrical", "materials", "equipment", "maintenance", "construction"} else 8.0 if sector != "general" else 0.0

        urgency = classification.get("submission_urgency") or {}
        urgency_label = _safe_str(urgency.get("label"), "normal")
        urgency_alignment = {
            "critical": 10.0,
            "urgent": 9.0,
            "elevated": 7.0,
            "standard": 5.0,
            "normal": 3.0,
        }.get(urgency_label, 3.0)

        document_fit = 10.0 if len(classification.get("mandatory_documents") or []) <= 8 else 7.0
        risk_penalty = min(_safe_float(risk.get("risk_score"), 0.0) * 0.35, 35.0)
        complexity_penalty = min(_safe_float((classification.get("tender_complexity") or {}).get("score"), 0.0) * 0.12, 12.0)

        base_score = buyer_alignment + keyword_alignment + supply_alignment + sector_alignment + urgency_alignment + document_fit
        opportunity_score = _clamp(base_score - risk_penalty - complexity_penalty)

        if opportunity_score >= 70:
            decision = "bid_now"
            priority = "high"
        elif opportunity_score >= 50:
            decision = "review"
            priority = "medium"
        else:
            decision = "no_bid"
            priority = "low"

        supplier_fit_score = _clamp(mean([buyer_alignment, sector_alignment, supply_alignment, urgency_alignment, document_fit]) - min(risk_penalty * 0.5, 25.0))
        analysis_id = f"opportunity-scoring:{_safe_str(tender.get('rfq_id') or tender.get('tender_id') or tender.get('title'), 'sample')}"
        analysis = {
            "analysis_id": analysis_id,
            "opportunity_scoring_id": analysis_id,
            "generated_at": _now_iso(),
            "title": _safe_str(tender.get("title") or tender.get("description") or tender.get("rfq_id"), "Untitled tender"),
            "buyer_name": _safe_str(tender.get("buyer_name") or tender.get("buyer") or tender.get("organ_of_state"), "Unknown buyer"),
            "opportunity_score": round(opportunity_score, 2),
            "supplier_fit_score": round(supplier_fit_score, 2),
            "bid_priority": priority,
            "bid_decision": decision,
            "rank_profitability_likelihood": "high" if opportunity_score >= 75 else "medium" if opportunity_score >= 55 else "low",
            "supplier_fit_scoring": {
                "buyer_alignment": round(buyer_alignment, 2),
                "keyword_alignment": round(keyword_alignment, 2),
                "supply_alignment": round(supply_alignment, 2),
                "sector_alignment": round(sector_alignment, 2),
                "urgency_alignment": round(urgency_alignment, 2),
                "document_fit": round(document_fit, 2),
                "risk_penalty": round(risk_penalty, 2),
                "complexity_penalty": round(complexity_penalty, 2),
                "supplier_fit_score": round(supplier_fit_score, 2),
            },
            "tender_complexity": classification.get("tender_complexity") or {},
            "risk_scoring": risk,
            "procurement_sector": sector,
            "submission_urgency": classification.get("submission_urgency") or {},
            "mandatory_documents": list(classification.get("mandatory_documents") or []),
            "risk_flags": list(risk.get("risk_flags") or []),
            "what_this_unlocks": [
                "understand tenders",
                "prioritize opportunities",
                "detect risky RFQs",
                "classify procurement sectors",
                "rank profitability likelihood",
                "assist bid/no-bid decisions",
                "prepare supplier strategy",
                "power executive summaries automatically",
            ],
            "warnings": [
                "High risk profile reduces the opportunity score" if _safe_float(risk.get("risk_score"), 0.0) >= 60.0 else "",
                "Tender complexity may compress execution window" if _safe_float((classification.get("tender_complexity") or {}).get("score"), 0.0) >= 60.0 else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]

        if record_history:
            history = self._load_history()
            history.append({
                "analysis_id": analysis["analysis_id"],
                "generated_at": analysis["generated_at"],
                "title": analysis["title"],
                "buyer_name": analysis["buyer_name"],
                "opportunity_score": analysis["opportunity_score"],
                "supplier_fit_score": analysis["supplier_fit_score"],
                "bid_priority": analysis["bid_priority"],
                "bid_decision": analysis["bid_decision"],
                "procurement_sector": analysis["procurement_sector"],
                "risk_score": analysis["risk_scoring"].get("risk_score", 0.0),
                "tender_complexity_band": analysis["tender_complexity"].get("band", "unknown"),
            })
            self._write_history(history)

        return analysis

    def score_opportunity(self, tender: Dict[str, Any]) -> Dict[str, Any]:
        analysis = self.analyze_opportunity(tender, record_history=True)
        history = self._load_history()
        return {
            "status": "ok",
            "opportunity_scoring_status": "ok" if analysis["opportunity_score"] >= 50 else "watch" if analysis["opportunity_score"] >= 35 else "blocked",
            "opportunity_scoring_score": analysis["opportunity_score"],
            "latest_opportunity_scoring": analysis,
            "opportunity_scoring_history": history,
            "opportunity_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_decision": analysis["bid_decision"],
            },
            "warnings": analysis["warnings"],
        }

    def list_opportunity_scores(self, limit: int = 20) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=max(1, int(limit))).get("items", [])
        analyses = [
            self.analyze_opportunity(item, record_history=False)
            for item in items
            if isinstance(item, dict)
        ]
        average = round(sum(entry["opportunity_score"] for entry in analyses) / len(analyses), 2) if analyses else 0.0
        latest = analyses[0] if analyses else {}
        return {
            "status": "ok",
            "count": len(analyses),
            "opportunity_scoring_status": "ok" if average >= 50 else "watch" if average >= 35 else "blocked",
            "opportunity_scoring_score": average,
            "latest_opportunity_scoring": latest,
            "opportunity_scoring_history": analyses,
            "opportunity_scoring_history_summary": {
                "analysis_count": len(analyses),
                "latest_decision": latest.get("bid_decision", "n/a"),
            },
            "warnings": [],
        }

    def latest_opportunity_scoring(self) -> Dict[str, Any]:
        return self.score_opportunity(self._latest_tender())

    def opportunity_scoring_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": "ok",
            "count": len(history),
            "opportunity_scoring_status": "ok" if latest.get("opportunity_score", 0.0) >= 50 else "watch" if latest.get("opportunity_score", 0.0) >= 35 else ("blocked" if history else "not_found"),
            "opportunity_scoring_score": latest.get("opportunity_score", 0.0) if history else 0.0,
            "latest_opportunity_scoring": latest,
            "opportunity_scoring_history": history,
            "opportunity_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_decision": latest.get("bid_decision", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


opportunity_scoring_service = OpportunityScoringService()
