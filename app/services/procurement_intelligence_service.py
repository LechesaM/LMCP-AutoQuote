from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.opportunity_scoring_service import OpportunityScoringService
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.risk_scoring_service import RiskScoringService
from app.services.tender_classification_service import TenderClassificationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "procurement-intelligence"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "procurement_intelligence_history.json"


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


def _history_entry(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "analysis_id": analysis["analysis_id"],
        "generated_at": analysis["generated_at"],
        "procurement_intelligence_status": analysis["procurement_intelligence_status"],
        "procurement_intelligence_grade": analysis["procurement_intelligence_grade"],
        "title": analysis["title"],
        "buyer_name": analysis["buyer_name"],
        "procurement_sector": analysis["procurement_sector"],
        "procurement_category": analysis["procurement_category"],
        "procurement_intelligence_score": analysis["procurement_intelligence_score"],
        "opportunity_score": analysis["opportunity_score"],
        "risk_score": analysis["risk_scoring"]["risk_score"],
        "tender_complexity_band": analysis["tender_complexity"]["band"],
        "bid_decision": analysis["opportunity_scoring"]["bid_decision"],
        "submission_urgency": analysis["submission_urgency"],
    }


class ProcurementIntelligenceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = TenderClassificationService(runtime_dir=self.runtime_dir)
        self.risk_scoring_service = RiskScoringService(runtime_dir=self.runtime_dir)
        self.opportunity_scoring_service = OpportunityScoringService(runtime_dir=self.runtime_dir)

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
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            best_item = None
            best_score = -1.0
            for item in items:
                if not isinstance(item, dict):
                    continue
                analysis = self.opportunity_scoring_service.analyze_opportunity(item, record_history=False)
                score = _safe_float(analysis.get("opportunity_score"), 0.0)
                if score > best_score:
                    best_item = item
                    best_score = score
            if best_item:
                return best_item
            first = items[0]
            if isinstance(first, dict):
                return first
        return self._sample_tender()

    def _analyze_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = self.lifecycle.list_items(limit=max(1, int(limit))).get("items", [])
        return [
            self.analyze_tender(item, record_history=False)
            for item in items
            if isinstance(item, dict)
        ]

    def _category_heatmap(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_score": 0.0, "total_risk": 0.0, "total_complexity": 0.0})
        for analysis in analyses:
            category = _safe_str(analysis.get("procurement_category"), "general")
            bucket = buckets[category]
            bucket["count"] += 1
            bucket["total_score"] += _safe_float(analysis.get("opportunity_score"), 0.0)
            bucket["total_risk"] += _safe_float(analysis.get("risk_scoring", {}).get("risk_score"), 0.0)
            bucket["total_complexity"] += _safe_float((analysis.get("tender_complexity") or {}).get("score"), 0.0)

        rows = []
        for category, bucket in buckets.items():
            count = bucket["count"]
            avg_score = round(bucket["total_score"] / count, 2) if count else 0.0
            avg_risk = round(bucket["total_risk"] / count, 2) if count else 0.0
            avg_complexity = round(bucket["total_complexity"] / count, 2) if count else 0.0
            rows.append({
                "procurement_category": category,
                "tender_count": count,
                "average_opportunity_score": avg_score,
                "average_risk_score": avg_risk,
                "average_tender_complexity": avg_complexity,
                "temperature": "hot" if avg_score >= 75 else "warm" if avg_score >= 55 else "cool" if avg_score >= 35 else "cold",
            })

        rows.sort(key=lambda row: (-row["tender_count"], -row["average_opportunity_score"], row["procurement_category"]))
        summary = {
            "generated_at": _now_iso(),
            "total_categories": len(rows),
            "total_tenders": len(analyses),
            "average_opportunity_score": round(sum(row["average_opportunity_score"] for row in rows) / len(rows), 2) if rows else 0.0,
            "average_risk_score": round(sum(row["average_risk_score"] for row in rows) / len(rows), 2) if rows else 0.0,
            "average_tender_complexity": round(sum(row["average_tender_complexity"] for row in rows) / len(rows), 2) if rows else 0.0,
            "dominant_category": rows[0]["procurement_category"] if rows else "n/a",
        }
        return {"summary": summary, "categories": rows, "top_categories": rows[:8]}

    def analyze_tender(self, tender: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        classification = self.classification_service.analyze_tender(tender, record_history=False)
        risk = self.risk_scoring_service.analyze_risk(tender, classification=classification, record_history=False)
        opportunity = self.opportunity_scoring_service.analyze_opportunity(tender, classification=classification, risk=risk, record_history=False)
        opportunity_score = _safe_float(opportunity.get("opportunity_score"), 0.0)
        risk_score = _safe_float(risk.get("risk_score"), 0.0)
        complexity_score = _safe_float((classification.get("tender_complexity") or {}).get("score"), 0.0)
        supplier_fit_score = _safe_float(opportunity.get("supplier_fit_score"), 0.0)

        intelligence_score = _clamp(opportunity_score)
        if intelligence_score >= 50:
            status = "ok"
            grade = "watch" if intelligence_score < 70 else "ready"
        elif intelligence_score >= 35:
            status = "watch"
            grade = "watch"
        else:
            status = "blocked"
            grade = "blocked"

        analysis_id = f"procurement-intelligence:{_safe_str(tender.get('rfq_id') or tender.get('tender_id') or tender.get('title'), 'sample')}"
        analysis = {
            "analysis_id": analysis_id,
            "generated_at": _now_iso(),
            "procurement_intelligence_status": status,
            "procurement_intelligence_score": round(intelligence_score, 2),
            "procurement_intelligence_grade": grade,
            "title": classification.get("title"),
            "buyer_name": classification.get("buyer_name"),
            "procurement_sector": classification.get("procurement_sector"),
            "procurement_category": classification.get("procurement_category"),
            "opportunity_score": round(opportunity_score, 2),
            "tender_complexity": classification.get("tender_complexity") or {},
            "risk_flags": list(risk.get("risk_flags") or []),
            "mandatory_documents": list(classification.get("mandatory_documents") or []),
            "submission_urgency": classification.get("submission_urgency") or {},
            "procurement_category_heatmap": self._category_heatmap([{
                "procurement_category": classification.get("procurement_category"),
                "opportunity_score": opportunity_score,
                "risk_scoring": risk,
                "tender_complexity": classification.get("tender_complexity") or {},
            }]),
            "supplier_fit_scoring": opportunity.get("supplier_fit_scoring") or {},
            "classification_summary": {
                "supply_tender": classification.get("supply_tender", False),
                "tender_type": classification.get("tender_type", "unknown"),
            },
            "risk_scoring": risk,
            "opportunity_scoring": opportunity,
            "decision_summary": {
                "bid_decision": opportunity.get("bid_decision", "no_bid"),
                "bid_priority": opportunity.get("bid_priority", "low"),
                "risk_level": risk.get("risk_level", "low"),
            },
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
                "No tender records available for procurement intelligence analysis" if not tender else "",
                "High risk profile reduces bidding confidence" if risk_score >= 60.0 else "",
                "Tender complexity is high" if complexity_score >= 60.0 else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]

        if record_history:
            history = self._load_history()
            history.append(_history_entry(analysis))
            self._write_history(history)

        return analysis

    def _response(self, analysis: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        warnings = list(analysis.get("warnings") or [])
        return {
            "status": "ok" if analysis["procurement_intelligence_status"] in {"ok", "watch"} else "blocked",
            "procurement_intelligence_status": analysis["procurement_intelligence_status"],
            "procurement_intelligence_score": analysis["procurement_intelligence_score"],
            "procurement_intelligence_grade": analysis["procurement_intelligence_grade"],
            "latest_procurement_intelligence": analysis,
            "procurement_intelligence_history": history,
            "procurement_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_bid_decision": analysis["decision_summary"]["bid_decision"],
                "latest_sector": analysis["procurement_sector"],
            },
            "opportunity_score": analysis["opportunity_score"],
            "tender_complexity": analysis["tender_complexity"],
            "risk_flags": analysis["risk_flags"],
            "mandatory_documents": analysis["mandatory_documents"],
            "submission_urgency": analysis["submission_urgency"],
            "procurement_category_heatmap": analysis["procurement_category_heatmap"],
            "supplier_fit_scoring": analysis["supplier_fit_scoring"],
            "warnings": warnings,
        }

    def list_procurement_intelligence(self, limit: int = 20) -> Dict[str, Any]:
        analyses = self._analyze_items(limit=limit)
        history = self._load_history()
        heatmap = self._category_heatmap(analyses)
        average_score = round(sum(entry["procurement_intelligence_score"] for entry in analyses) / len(analyses), 2) if analyses else 0.0
        latest = max(analyses, key=lambda entry: entry["opportunity_score"]) if analyses else self.analyze_tender(self._sample_tender(), record_history=False)
        return {
            "status": "ok" if analyses else "not_found",
            "count": len(analyses),
            "procurement_intelligence_status": "ok" if average_score >= 50 else "blocked" if analyses else "not_found",
            "procurement_intelligence_score": average_score,
            "procurement_intelligence_grade": "ready" if average_score >= 70 else "watch" if average_score >= 50 else "blocked" if analyses else "not_found",
            "latest_procurement_intelligence": latest,
            "procurement_intelligence_history": analyses,
            "procurement_intelligence_history_summary": {
                "analysis_count": len(analyses),
                "latest_bid_decision": latest["decision_summary"]["bid_decision"] if analyses else "n/a",
                "latest_sector": latest["procurement_sector"] if analyses else "n/a",
            },
            "opportunity_score": latest["opportunity_score"] if analyses else 0.0,
            "tender_complexity": latest["tender_complexity"] if analyses else {},
            "risk_flags": latest["risk_flags"] if analyses else [],
            "mandatory_documents": latest["mandatory_documents"] if analyses else [],
            "submission_urgency": latest["submission_urgency"] if analyses else {},
            "procurement_category_heatmap": heatmap,
            "supplier_fit_scoring": latest["supplier_fit_scoring"] if analyses else {},
            "warnings": [],
            "history": history,
        }

    def latest_procurement_intelligence(self) -> Dict[str, Any]:
        analyses = self._analyze_items(limit=20)
        analysis = max(analyses, key=lambda entry: entry["opportunity_score"]) if analyses else self.analyze_tender(self._sample_tender(), record_history=False)
        analysis = dict(analysis)
        analysis["procurement_category_heatmap"] = self._category_heatmap(analyses or [analysis])
        analysis["analysis_id"] = analysis.get("analysis_id") or f"procurement-intelligence:{_safe_str(analysis.get('title'), 'sample')}"
        analysis["generated_at"] = _now_iso()
        history = self._load_history()
        if analyses:
            history.append(_history_entry(analysis))
            self._write_history(history)
        return self._response(analysis, history)

    def procurement_intelligence_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": "ok",
            "count": len(history),
            "procurement_intelligence_status": "ok" if latest.get("procurement_intelligence_score", 0.0) >= 50 else ("blocked" if history else "not_found"),
            "procurement_intelligence_score": latest.get("procurement_intelligence_score", 0.0) if history else 0.0,
            "procurement_intelligence_grade": "ready" if latest.get("procurement_intelligence_score", 0.0) >= 70 else "watch" if latest.get("procurement_intelligence_score", 0.0) >= 50 else ("blocked" if history else "not_found"),
            "latest_procurement_intelligence": latest,
            "procurement_intelligence_history": history,
            "procurement_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_bid_decision": latest.get("bid_decision", "n/a") if history else "n/a",
                "latest_sector": latest.get("procurement_sector", "n/a") if history else "n/a",
            },
            "opportunity_score": latest.get("opportunity_score", 0.0) if history else 0.0,
            "tender_complexity": latest.get("tender_complexity", {}) if history else {},
            "risk_flags": latest.get("risk_flags", []) if history else [],
            "mandatory_documents": latest.get("mandatory_documents", []) if history else [],
            "submission_urgency": latest.get("submission_urgency", {}) if history else {},
            "procurement_category_heatmap": latest.get("procurement_category_heatmap", {}) if history else {},
            "supplier_fit_scoring": latest.get("supplier_fit_scoring", {}) if history else {},
            "warnings": [],
        }


procurement_intelligence_service = ProcurementIntelligenceService()
