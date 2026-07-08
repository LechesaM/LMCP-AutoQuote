from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.boq_item_classification_service import BoqItemClassificationService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "boq-semantic-understanding"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "boq_ambiguity_detection_history.json"


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


class BoqAmbiguityDetectionService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = BoqItemClassificationService(runtime_dir=self.runtime_dir)

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

    def _latest_item(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return {
            "item_number": 1,
            "description": "Office chairs",
            "specification": "Ergonomic task chair",
            "unit": "Each",
            "quantity": 20,
        }

    def _detect(self, item: Dict[str, Any], classification: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        classification = classification or self.classification_service.classify_boq_item(item, record_history=False)
        description = _safe_str(item.get("description") or classification.get("description"))
        specification = _safe_str(item.get("specification") or classification.get("specification"))
        unit = _safe_str(item.get("unit") or classification.get("unit"))
        quantity = item.get("quantity")
        blob = " ".join([description, specification, unit, _safe_str(quantity)]).lower()

        ambiguous_item_flags = list(classification.get("ambiguous_item_flags") or [])
        missing_specification_flags = list(classification.get("missing_specification_flags") or [])

        if re.search(r"\b(?:or equivalent|approx(?:imately)?|subject to confirmation|to be confirmed|tbc)\b", blob):
            ambiguous_item_flags.append("measurement_phrase_ambiguous")
        if re.search(r"\b(?:various|mixed|bundle|lot|set)\b", blob):
            ambiguous_item_flags.append("quantity_expression_ambiguous")
        if not specification:
            missing_specification_flags.append("missing_specification")
        if not description:
            missing_specification_flags.append("missing_description")
        if not unit:
            missing_specification_flags.append("missing_unit_of_measure")
        if quantity in (None, ""):
            missing_specification_flags.append("missing_quantity")

        ambiguous_item_flags = sorted({flag for flag in ambiguous_item_flags if flag})
        missing_specification_flags = sorted({flag for flag in missing_specification_flags if flag})
        ambiguity_score = _clamp(20.0 * len(ambiguous_item_flags) + 15.0 * len(missing_specification_flags))

        return {
            "analysis_id": f"boq-ambiguity:{_safe_str(item.get('item_number') or item.get('description') or item.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "item_number": item.get("item_number"),
            "ambiguous_item_flags": ambiguous_item_flags,
            "missing_specification_flags": missing_specification_flags,
            "ambiguity_score": round(ambiguity_score, 2),
            "ambiguity_readiness": {
                "ready": ambiguity_score < 35.0,
                "score": round(100.0 - ambiguity_score, 2),
            },
            "warnings": [
                "Ambiguous BOQ item requires human review" if ambiguity_score >= 35.0 else "",
            ],
        }

    def detect_boq_ambiguity(self, item: Dict[str, Any], classification: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        analysis = self._detect(item, classification=classification)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "item_number": analysis["item_number"],
                    "ambiguity_score": analysis["ambiguity_score"],
                    "ambiguous_item_flags": analysis["ambiguous_item_flags"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_boq_ambiguity_detection(self) -> Dict[str, Any]:
        latest_item = self._latest_item()
        classification = self.classification_service.classify_boq_item(latest_item, record_history=False)
        analysis = self.detect_boq_ambiguity(latest_item, classification=classification, record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["ambiguity_score"] < 35 else "watch",
            "ambiguity_detection_status": "clear" if analysis["ambiguity_score"] < 35 else "watch",
            "ambiguity_score": analysis["ambiguity_score"],
            "latest_boq_ambiguity_detection": analysis,
            "boq_ambiguity_detection_history": history,
            "boq_ambiguity_detection_history_summary": {
                "analysis_count": len(history),
                "latest_ambiguity_score": analysis["ambiguity_score"],
            },
            "warnings": analysis["warnings"],
        }

    def boq_ambiguity_detection_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("ambiguity_score"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "ambiguity_detection_status": "clear" if score < 35 else "watch" if history else "not_found",
            "ambiguity_score": score,
            "latest_boq_ambiguity_detection": latest,
            "boq_ambiguity_detection_history": history,
            "boq_ambiguity_detection_history_summary": {
                "analysis_count": len(history),
                "latest_ambiguity_score": latest.get("ambiguity_score", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


boq_ambiguity_detection_service = BoqAmbiguityDetectionService()
