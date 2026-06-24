from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.tender_classification_service import TenderClassificationService
from app.services.tender_intelligence import detect_supply_tender


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "procurement-intelligence"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "risk_scoring_history.json"


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
        tender.get("submission_method"),
        tender.get("category"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _risk_level(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


class RiskScoringService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = TenderClassificationService(runtime_dir=self.runtime_dir)

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

    def analyze_risk(
        self,
        tender: Dict[str, Any],
        classification: Optional[Dict[str, Any]] = None,
        record_history: bool = False,
    ) -> Dict[str, Any]:
        blob = _text_blob(tender)
        classification = classification or self.classification_service.analyze_tender(tender, record_history=False)
        complexity = classification.get("tender_complexity") or {}
        urgency = classification.get("submission_urgency") or {}
        mandatory_documents = list(classification.get("mandatory_documents") or [])

        risk_score = 10.0
        risk_flags: List[str] = []

        if classification.get("supply_tender") is False:
            risk_score += 25.0
            risk_flags.append("mixed_or_service_scope")

        if "briefing" in blob or "site visit" in blob or "site inspection" in blob:
            risk_score += 25.0
            risk_flags.append("mandatory_briefing")

        if "framework" in blob or "panel" in blob:
            risk_score += 8.0
            risk_flags.append("framework_or_panel")

        if complexity.get("band") in {"high", "extreme"}:
            risk_score += 15.0
            risk_flags.append(f"complexity_{complexity.get('band', 'high')}")

        urgency_label = _safe_str(urgency.get("label"), "normal")
        if urgency_label in {"urgent", "critical"}:
            risk_score += 20.0
            risk_flags.append(f"deadline_{urgency_label}")
        elif urgency_label == "elevated":
            risk_score += 10.0
            risk_flags.append("deadline_elevated")

        if len(mandatory_documents) >= 8:
            risk_score += 8.0
            risk_flags.append("document_burden_high")
        elif len(mandatory_documents) <= 4:
            risk_score += 12.0
            risk_flags.append("document_set_incomplete_or_sparse")

        if detect_supply_tender(tender.get("title", ""), tender.get("description", "")) is False:
            risk_flags.append("not_clear_supply_tender")

        if any(term in blob for term in ["medical", "pharmaceutical", "fuel", "diesel", "petrol"]):
            risk_score += 18.0
            risk_flags.append("restricted_or_sensitive_category")

        if any(term in blob for term in ["lot", "lots", "multi-stage", "two stage"]):
            risk_score += 10.0
            risk_flags.append("multi_stage_or_multi_lot")

        risk_score = _clamp(risk_score)
        risk_level = _risk_level(risk_score)
        risk_recommendation = "no_bid" if risk_level in {"high", "critical"} else "review"
        if risk_level == "low":
            risk_recommendation = "bid"

        analysis_id = f"risk-scoring:{_safe_str(tender.get('rfq_id') or tender.get('tender_id') or tender.get('title'), 'sample')}"
        analysis = {
            "analysis_id": analysis_id,
            "risk_scoring_id": analysis_id,
            "generated_at": _now_iso(),
            "title": _safe_str(tender.get("title") or tender.get("description") or tender.get("rfq_id"), "Untitled tender"),
            "buyer_name": _safe_str(tender.get("buyer_name") or tender.get("buyer") or tender.get("organ_of_state"), "Unknown buyer"),
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "risk_flags": risk_flags,
            "risk_recommendation": risk_recommendation,
            "risk_factors": {
                "supply_scope": classification.get("supply_tender", False),
                "complexity_band": complexity.get("band", "unknown"),
                "submission_urgency": urgency.get("label", "normal"),
                "mandatory_document_count": len(mandatory_documents),
            },
            "tender_complexity": complexity,
            "submission_urgency": urgency,
            "mandatory_documents": mandatory_documents,
            "warnings": [
                "High complexity tender" if risk_level in {"high", "critical"} else "",
                "Mandatory briefing or site inspection detected" if "mandatory_briefing" in risk_flags else "",
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
                "risk_score": analysis["risk_score"],
                "risk_level": analysis["risk_level"],
                "risk_flags": analysis["risk_flags"],
                "risk_recommendation": analysis["risk_recommendation"],
                "tender_complexity_band": analysis["tender_complexity"].get("band", "unknown"),
                "submission_urgency": analysis["submission_urgency"],
            })
            self._write_history(history)

        return analysis

    def score_risk(self, tender: Dict[str, Any]) -> Dict[str, Any]:
        analysis = self.analyze_risk(tender, record_history=True)
        history = self._load_history()
        return {
            "status": "ok",
            "risk_scoring_status": "blocked" if analysis["risk_level"] in {"high", "critical"} else "watch" if analysis["risk_level"] == "medium" else "ok",
            "risk_scoring_score": analysis["risk_score"],
            "latest_risk_scoring": analysis,
            "risk_scoring_history": history,
            "risk_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_risk_level": analysis["risk_level"],
            },
            "warnings": analysis["warnings"],
        }

    def list_risk_scores(self, limit: int = 20) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=max(1, int(limit))).get("items", [])
        analyses = [
            self.analyze_risk(item, record_history=False)
            for item in items
            if isinstance(item, dict)
        ]
        average = round(sum(entry["risk_score"] for entry in analyses) / len(analyses), 2) if analyses else 0.0
        latest = analyses[0] if analyses else {}
        return {
            "status": "ok",
            "count": len(analyses),
            "risk_scoring_status": "blocked" if average >= 60.0 else "watch" if average >= 35.0 else "ok",
            "risk_scoring_score": average,
            "latest_risk_scoring": latest,
            "risk_scoring_history": analyses,
            "risk_scoring_history_summary": {
                "analysis_count": len(analyses),
                "latest_risk_level": latest.get("risk_level", "n/a"),
            },
            "warnings": [],
        }

    def latest_risk_scoring(self) -> Dict[str, Any]:
        return self.score_risk(self._latest_tender())

    def risk_scoring_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": "ok",
            "count": len(history),
            "risk_scoring_status": "blocked" if latest.get("risk_level") in {"high", "critical"} else "watch" if latest.get("risk_level") == "medium" else ("ok" if history else "not_found"),
            "risk_scoring_score": latest.get("risk_score", 0.0) if history else 0.0,
            "latest_risk_scoring": latest,
            "risk_scoring_history": history,
            "risk_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_risk_level": latest.get("risk_level", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


risk_scoring_service = RiskScoringService()

