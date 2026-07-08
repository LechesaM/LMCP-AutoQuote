from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.tender_intelligence import classify_sector, detect_supply_tender


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "procurement-intelligence"

SECTOR_KEYWORDS = {
    "construction": ["construction", "building", "civil", "infrastructure", "road", "refurbishment", "maintenance"],
    "information_technology": ["software", "hardware", "laptop", "server", "network", "cloud", "cyber", "it"],
    "supplies": ["stationery", "consumables", "goods", "materials", "equipment", "supply"],
    "professional_services": ["consulting", "advisory", "professional services", "assessment", "audit", "training"],
    "facilities": ["cleaning", "security", "catering", "waste", "facilities", "grounds"],
    "logistics": ["delivery", "transport", "courier", "fleet", "distribution", "warehouse"],
    "healthcare": ["medical", "clinic", "hospital", "pharmaceutical", "laboratory", "health"],
    "energy_water": ["energy", "electricity", "water", "power", "renewable", "solar", "substation"],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "tender_classification_history.json"


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
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
        tender.get("sector"),
        tender.get("submission_method"),
        tender.get("notes"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _mandatory_documents(blob: str, tender: Dict[str, Any], category: str) -> List[str]:
    documents = [
        "company_registration",
        "tax_compliance",
        "pricing_schedule",
        "declaration_forms",
        "supplier_profile",
    ]
    if "briefing" in blob or "site visit" in blob or "site inspection" in blob:
        documents.append("briefing_attendance")
    if "bbb" in blob or "bee" in blob or "b-bbee" in blob:
        documents.append("bee_certificate")
    if "construction" in category or "construction" in blob:
        documents.extend(["cidb_registration", "safety_plan"])
    if "medical" in blob or "health" in blob or "clinic" in blob:
        documents.extend(["regulatory_certification", "product_specification_sheet"])
    if "it" in category or "software" in blob or "hardware" in blob:
        documents.extend(["technical_specification", "implementation_method_statement"])
    if _safe_str(tender.get("submission_method"), "").lower() in {"portal", "email"}:
        documents.append("submission_acknowledgement")
    ordered: List[str] = []
    for doc in documents:
        if doc not in ordered:
            ordered.append(doc)
    return ordered


def _complexity_signals(blob: str, tender: Dict[str, Any], category: str, mandatory_documents: List[str]) -> Dict[str, Any]:
    closing_date = tender.get("closing_date") or tender.get("deadline") or tender.get("submission_deadline")
    days_left = None
    if closing_date:
        try:
            parsed = datetime.fromisoformat(str(closing_date).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            days_left = int((parsed - datetime.now(timezone.utc)).total_seconds() / 86400)
        except Exception:
            days_left = None

    signal_points = 20.0
    if any(term in blob for term in ["framework", "panel", "multi-stage", "lot", "lots", "two stage", "tender briefing", "mandatory briefing"]):
        signal_points += 15.0
    if category in {"construction", "information_technology", "professional_services", "healthcare", "energy_water"}:
        signal_points += 10.0
    if len(mandatory_documents) >= 8:
        signal_points += 20.0
    elif len(mandatory_documents) >= 6:
        signal_points += 12.0
    elif len(mandatory_documents) >= 4:
        signal_points += 6.0
    if days_left is not None:
        if days_left <= 3:
            signal_points += 20.0
        elif days_left <= 7:
            signal_points += 12.0
        elif days_left <= 14:
            signal_points += 5.0
    if len(blob) > 1500:
        signal_points += 10.0
    if "as and when" in blob or "framework agreement" in blob:
        signal_points += 10.0

    complexity_score = _clamp(signal_points)
    if complexity_score >= 80:
        band = "extreme"
    elif complexity_score >= 60:
        band = "high"
    elif complexity_score >= 35:
        band = "moderate"
    else:
        band = "low"

    urgency_score = 20.0
    urgency_label = "normal"
    if days_left is not None:
        if days_left <= 3:
            urgency_score = 100.0
            urgency_label = "critical"
        elif days_left <= 7:
            urgency_score = 85.0
            urgency_label = "urgent"
        elif days_left <= 14:
            urgency_score = 65.0
            urgency_label = "elevated"
        elif days_left <= 30:
            urgency_score = 40.0
            urgency_label = "standard"
    elif "urgent" in blob or "immediate" in blob:
        urgency_score = 80.0
        urgency_label = "urgent"

    return {
        "days_left": days_left,
        "signal_points": round(signal_points, 2),
        "complexity_score": round(complexity_score, 2),
        "complexity_band": band,
        "submission_urgency": {
            "label": urgency_label,
            "score": round(urgency_score, 2),
            "days_left": days_left,
        },
    }


def _history_entry(tender: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tender_classification_id": analysis["tender_classification_id"],
        "analysis_id": analysis["analysis_id"],
        "generated_at": analysis["generated_at"],
        "title": analysis["title"],
        "buyer_name": analysis["buyer_name"],
        "procurement_sector": analysis["procurement_sector"],
        "procurement_category": analysis["procurement_category"],
        "supply_tender": analysis["supply_tender"],
        "tender_complexity": analysis["tender_complexity"],
        "submission_urgency": analysis["submission_urgency"],
        "mandatory_documents": analysis["mandatory_documents"],
        "tender_complexity_score": analysis["tender_complexity"]["score"],
        "tender_reference": tender.get("rfq_id") or tender.get("tender_id") or tender.get("reference") or analysis["title"],
    }


class TenderClassificationService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()

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

    def analyze_tender(self, tender: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        blob = _text_blob(tender)
        title = _safe_str(tender.get("title") or tender.get("description") or tender.get("rfq_id"), "Untitled tender")
        buyer_name = _safe_str(tender.get("buyer_name") or tender.get("buyer") or tender.get("organ_of_state"), "Unknown buyer")
        procurement_sector = classify_sector(title, _safe_str(tender.get("description") or tender.get("raw_text"), ""))
        category = _safe_str(tender.get("category") or procurement_sector or "general", "general")
        if category == "general":
            for name, keywords in SECTOR_KEYWORDS.items():
                if any(keyword in blob for keyword in keywords):
                    category = name
                    break

        supply_tender = detect_supply_tender(title, _safe_str(tender.get("description") or tender.get("raw_text"), ""))
        mandatory_documents = _mandatory_documents(blob, tender, category)
        complexity = _complexity_signals(blob, tender, category, mandatory_documents)

        analysis_id = f"tender-classification:{_safe_str(tender.get('rfq_id') or tender.get('tender_id') or title, 'sample')}"
        analysis = {
            "analysis_id": analysis_id,
            "tender_classification_id": analysis_id,
            "generated_at": _now_iso(),
            "title": title,
            "buyer_name": buyer_name,
            "procurement_sector": procurement_sector,
            "procurement_category": category,
            "tender_type": "supply" if supply_tender else "mixed_or_service",
            "supply_tender": supply_tender,
            "tender_complexity": {
                "score": complexity["complexity_score"],
                "band": complexity["complexity_band"],
                "signals": {
                    "signal_points": complexity["signal_points"],
                    "days_left": complexity["days_left"],
                },
            },
            "mandatory_documents": mandatory_documents,
            "submission_urgency": complexity["submission_urgency"],
            "classification_signals": {
                "contains_supply_keywords": supply_tender,
                "contains_framework_language": any(term in blob for term in ["framework", "panel"]),
                "contains_compulsory_briefing": any(term in blob for term in ["briefing", "site visit", "site inspection"]),
                "document_count": len(mandatory_documents),
            },
            "classification_notes": [
                "Supply tender detected" if supply_tender else "Mixed or service-oriented procurement detected",
                f"Category classified as {category}",
            ],
            "warnings": [
                "Tender may require mandatory briefing attendance" if complexity["submission_urgency"]["label"] in {"urgent", "critical"} else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]

        if record_history:
            history = self._load_history()
            history.append(_history_entry(tender, analysis))
            self._write_history(history)

        return analysis

    def classify_tender(self, tender: Dict[str, Any]) -> Dict[str, Any]:
        analysis = self.analyze_tender(tender, record_history=True)
        history = self._load_history()
        return {
            "status": "ok",
            "tender_classification_status": "watch" if analysis["tender_complexity"]["band"] == "extreme" else "ok",
            "tender_classification_score": analysis["tender_complexity"]["score"],
            "latest_tender_classification": analysis,
            "tender_classification_history": history,
            "tender_classification_history_summary": {
                "analysis_count": len(history),
                "latest_category": analysis["procurement_category"],
            },
            "warnings": analysis["warnings"],
        }

    def list_tender_classifications(self, limit: int = 20) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=max(1, int(limit))).get("items", [])
        analyses = [
            self.analyze_tender(item, record_history=False)
            for item in items
            if isinstance(item, dict)
        ]
        return {
            "status": "ok",
            "count": len(analyses),
            "tender_classification_status": "watch" if analyses and any(entry["tender_complexity"]["band"] == "extreme" for entry in analyses) else ("ok" if analyses else "not_found"),
            "tender_classification_score": round(sum(entry["tender_complexity"]["score"] for entry in analyses) / len(analyses), 2) if analyses else 0.0,
            "tender_classification_history": analyses,
            "latest_tender_classification": analyses[0] if analyses else {},
            "tender_classification_history_summary": {
                "analysis_count": len(analyses),
                "latest_category": analyses[0]["procurement_category"] if analyses else "n/a",
            },
            "warnings": [],
        }

    def latest_tender_classification(self) -> Dict[str, Any]:
        return self.classify_tender(self._latest_tender())

    def tender_classification_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": "ok",
            "count": len(history),
            "tender_classification_status": "watch" if history and latest.get("tender_classification_score", 0.0) >= 85.0 else ("ok" if history else "not_found"),
            "tender_classification_score": latest.get("tender_complexity_score", 0.0) if history else 0.0,
            "latest_tender_classification": latest,
            "tender_classification_history": history,
            "tender_classification_history_summary": {
                "analysis_count": len(history),
                "latest_category": latest.get("procurement_category", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


tender_classification_service = TenderClassificationService()
