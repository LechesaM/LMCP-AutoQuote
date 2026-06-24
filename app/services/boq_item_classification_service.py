from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "boq-semantic-understanding"
KNOWN_UNITS = {
    "each",
    "ea",
    "unit",
    "units",
    "box",
    "boxes",
    "pack",
    "packs",
    "lot",
    "lots",
    "set",
    "sets",
    "pair",
    "pairs",
    "roll",
    "rolls",
    "ream",
    "reams",
    "kg",
    "g",
    "ton",
    "tons",
    "litre",
    "litres",
    "liter",
    "liters",
    "ml",
    "m",
    "mm",
    "cm",
    "metre",
    "metres",
    "meter",
    "meters",
    "month",
    "months",
    "year",
    "years",
}
TRADE_KEYWORDS = {
    "civil": ["civil", "construction", "earthworks", "concrete", "brick", "paving", "road"],
    "electrical": ["electrical", "cable", "lighting", "switch", "breaker", "panel", "wire", "socket"],
    "plumbing": ["plumbing", "pipe", "fitting", "valve", "pump", "drain", "sanitary"],
    "ict": ["computer", "laptop", "server", "network", "router", "switch", "software", "ict", "technology"],
    "stationery": ["stationery", "paper", "pen", "file", "folder", "office supply", "print"],
    "cleaning": ["cleaning", "detergent", "hygiene", "sanitiser", "soap", "paper towel"],
    "security": ["security", "guard", "cctv", "alarm", "access control", "fence"],
    "professional_services": ["consulting", "professional", "advisory", "engineering services", "legal"],
    "transport": ["transport", "delivery", "haulage", "vehicle", "logistics"],
    "general_goods": ["supply", "goods", "consumable", "equipment", "furniture", "tool"],
}
AMBIGUITY_PHRASES = [
    "approx",
    "approximately",
    "about",
    "as required",
    "tbc",
    "to be confirmed",
    "subject to confirmation",
    "or equivalent",
    "various",
    "mixed",
    "bundle",
    "lot",
    "set",
    "estimated",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "boq_item_classification_history.json"


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
    result: List[str] = []
    for value in values:
        cleaned = _safe_str(value)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _text_blob(item: Dict[str, Any]) -> str:
    parts = [
        item.get("description"),
        item.get("specification"),
        item.get("title"),
        item.get("item_description"),
        item.get("raw_text"),
        item.get("source_line"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _extract_rows(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in ("boq_rows", "normalized_boq_rows", "pricing_ready_rows", "review_rows", "items", "line_items", "rows"):
        value = record.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    rows.append(deepcopy(entry))
    if rows:
        return rows
    return [deepcopy(record)]


def _normalize_unit(unit: str) -> str:
    cleaned = _safe_str(unit).lower()
    aliases = {
        "each": "each",
        "ea": "each",
        "unit": "each",
        "units": "each",
        "metre": "m",
        "meter": "m",
        "metres": "m",
        "meters": "m",
        "litre": "l",
        "liter": "l",
        "litres": "l",
        "liters": "l",
    }
    return aliases.get(cleaned, cleaned)


def _infer_trade_package(blob: str) -> Dict[str, str]:
    for trade, keywords in TRADE_KEYWORDS.items():
        if any(keyword in blob for keyword in keywords):
            package = "works" if trade in {"civil", "electrical", "plumbing"} else "services" if trade == "professional_services" else "goods"
            return {"trade_category": trade, "package_category": package}
    return {"trade_category": "general_goods", "package_category": "goods"}


def _detect_missing_flags(item: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    if not _safe_str(item.get("description")):
        flags.append("missing_description")
    if not _safe_str(item.get("specification")):
        flags.append("missing_specification")
    if not _safe_str(item.get("unit")):
        flags.append("missing_unit_of_measure")
    if item.get("quantity") in (None, ""):
        flags.append("missing_quantity")
    return flags


def _detect_ambiguity_flags(item: Dict[str, Any]) -> List[str]:
    blob = _text_blob(item)
    flags: List[str] = []
    if not _safe_str(item.get("description")) and _safe_str(item.get("specification")):
        flags.append("description_absent")
    if any(phrase in blob for phrase in AMBIGUITY_PHRASES):
        flags.append("ambiguous_text_phrase_present")
    if re.search(r"\b(?:or equivalent|tbc|approx(?:imately)?|subject to confirmation)\b", blob):
        flags.append("ambiguous_measurement_phrase")
    if not _safe_str(item.get("specification")) and any(token in blob for token in ("specification", "spec", "scope of work")):
        flags.append("specification_missing")
    if not _safe_str(item.get("unit")):
        flags.append("unit_absent")
    if item.get("quantity") in (None, ""):
        flags.append("quantity_absent")
    return _unique(flags)


def _score_classification(item: Dict[str, Any]) -> Dict[str, Any]:
    description = _safe_str(item.get("description"))
    specification = _safe_str(item.get("specification"))
    unit = _safe_str(item.get("unit"))
    quantity = _safe_float(item.get("quantity"), 0.0) if item.get("quantity") not in (None, "") else None
    blob = _text_blob(item)
    trade = _infer_trade_package(blob)
    normalized_unit = _normalize_unit(unit)
    unit_recognized = bool(normalized_unit in KNOWN_UNITS or normalized_unit in {"m", "l", "kg", "mm", "cm"})
    quantity_numeric = quantity is not None
    trade_confidence = 95.0 if trade["trade_category"] != "general_goods" else 70.0 if any(token in blob for token in ("supply", "goods", "equipment", "stationery")) else 45.0

    description_score = 100.0 if description else 0.0
    specification_score = 75.0 if specification else 20.0
    unit_score = 100.0 if unit_recognized else 60.0 if unit else 20.0
    quantity_score = 100.0 if quantity_numeric else 20.0
    score = _clamp(mean([description_score, specification_score, unit_score, quantity_score, trade_confidence]))

    trade_package_mapping_readiness = _clamp(mean([trade_confidence, 100.0 if trade["trade_category"] != "general_goods" else 60.0, 100.0 if _safe_str(item.get("description")) else 15.0]))
    uom_readiness = _clamp(mean([unit_score, 100.0 if normalized_unit else 0.0]))
    quantity_readiness = _clamp(mean([quantity_score, 100.0 if quantity_numeric else 0.0]))
    pricing_readiness = _clamp(mean([score, trade_package_mapping_readiness, uom_readiness, quantity_readiness]))

    ambiguous_item_flags = _detect_ambiguity_flags(item)
    missing_specification_flags = _detect_missing_flags(item)
    unresolved_blockers: List[str] = []
    if "missing_description" in missing_specification_flags:
        unresolved_blockers.append("missing_description")
    if "missing_specification" in missing_specification_flags:
        unresolved_blockers.append("missing_specification")
    if "missing_unit_of_measure" in missing_specification_flags:
        unresolved_blockers.append("missing_unit_of_measure")
    if "missing_quantity" in missing_specification_flags:
        unresolved_blockers.append("missing_quantity")
    unresolved_blockers.extend(ambiguous_item_flags)

    if score >= 80 and not unresolved_blockers:
        status = "ready"
    elif score >= 55:
        status = "needs_review"
    else:
        status = "unusable"

    return {
        "description": description,
        "specification": specification,
        "unit": unit,
        "normalized_unit_of_measure": normalized_unit,
        "quantity": quantity,
        "trade_package_category": trade["trade_category"],
        "package_category": trade["package_category"],
        "classification_score": round(score, 2),
        "classification_status": status,
        "classification_grade": "ready" if status == "ready" else "watch" if status == "needs_review" else "blocked",
        "boq_item_classification_readiness": {
            "ready": status == "ready",
            "score": round(score, 2),
        },
        "trade_package_mapping_readiness": {
            "ready": trade_package_mapping_readiness >= 70.0,
            "score": round(trade_package_mapping_readiness, 2),
        },
        "unit_of_measure_normalization_readiness": {
            "ready": uom_readiness >= 70.0,
            "score": round(uom_readiness, 2),
        },
        "quantity_interpretation_readiness": {
            "ready": quantity_readiness >= 70.0,
            "score": round(quantity_readiness, 2),
        },
        "pricing_preparation_readiness": {
            "ready": pricing_readiness >= 70.0 and not unresolved_blockers,
            "score": round(pricing_readiness, 2),
        },
        "ambiguous_item_flags": ambiguous_item_flags,
        "missing_specification_flags": missing_specification_flags,
        "unresolved_boq_semantic_blockers": unresolved_blockers,
        "warnings": [
            "BOQ item requires review" if status != "ready" else "",
            "Ambiguous item text detected" if ambiguous_item_flags else "",
        ],
    }


class BoqItemClassificationService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()

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
            "item_number": 1,
            "description": "Office chairs",
            "specification": "Ergonomic task chair",
            "unit": "Each",
            "quantity": 20,
        }

    def _latest_item(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_item()

    def classify_boq_item(self, item: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        analysis = _score_classification(deepcopy(item or {}))
        analysis_id = f"boq-item-classification:{_safe_str(item.get('item_number') or item.get('description') or item.get('title'), 'sample')}"
        analysis.update(
            {
                "analysis_id": analysis_id,
                "generated_at": _now_iso(),
                "item_number": item.get("item_number"),
                "source_reference": _safe_str(item.get("rfq_id") or item.get("rfq_reference") or item.get("title"), "n/a"),
                "warnings": [warning for warning in analysis["warnings"] if warning],
            }
        )
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "item_number": analysis["item_number"],
                    "classification_status": analysis["classification_status"],
                    "classification_score": analysis["classification_score"],
                    "trade_package_category": analysis["trade_package_category"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_boq_item_classification(self) -> Dict[str, Any]:
        analysis = self.classify_boq_item(self._latest_item(), record_history=True)
        history = self._load_history()
        status = "ok" if analysis["classification_status"] == "ready" else "watch" if analysis["classification_status"] == "needs_review" else "blocked"
        return {
            "status": status,
            "boq_item_classification_status": analysis["classification_status"],
            "boq_item_classification_score": analysis["classification_score"],
            "latest_boq_item_classification": analysis,
            "boq_item_classification_history": history,
            "boq_item_classification_history_summary": {
                "analysis_count": len(history),
                "latest_trade_package_category": analysis["trade_package_category"],
            },
            "warnings": analysis["warnings"],
        }

    def boq_item_classification_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("classification_score"), 0.0) if history else 0.0
        status = "ok" if score >= 80 else "watch" if score >= 55 else ("blocked" if history else "not_found")
        return {
            "status": "ok",
            "count": len(history),
            "boq_item_classification_status": status,
            "boq_item_classification_score": score,
            "latest_boq_item_classification": latest,
            "boq_item_classification_history": history,
            "boq_item_classification_history_summary": {
                "analysis_count": len(history),
                "latest_trade_package_category": latest.get("trade_package_category", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


boq_item_classification_service = BoqItemClassificationService()
