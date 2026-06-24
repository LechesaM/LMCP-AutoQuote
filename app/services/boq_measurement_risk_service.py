from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.boq_item_classification_service import BoqItemClassificationService
from app.services.boq_trade_mapping_service import BoqTradeMappingService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "boq-semantic-understanding"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "boq_measurement_risk_history.json"


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


def _extract_rows(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in ("boq_rows", "normalized_boq_rows", "pricing_ready_rows", "review_rows", "items", "line_items", "rows"):
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    rows.append(entry)
    return rows or [item]


class BoqMeasurementRiskService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = BoqItemClassificationService(runtime_dir=self.runtime_dir)
        self.trade_mapping_service = BoqTradeMappingService(runtime_dir=self.runtime_dir)

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

    def _score_risk(self, item: Dict[str, Any], classification: Optional[Dict[str, Any]] = None, trade_mapping: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        classification = classification or self.classification_service.classify_boq_item(item, record_history=False)
        trade_mapping = trade_mapping or self.trade_mapping_service.map_boq_trade(item, classification=classification, record_history=False)
        description = _safe_str(item.get("description") or classification.get("description"))
        specification = _safe_str(item.get("specification") or classification.get("specification"))
        unit = _safe_str(item.get("unit") or classification.get("unit"))
        quantity = item.get("quantity")
        ambiguous_flags = list(classification.get("ambiguous_item_flags") or [])
        missing_flags = list(classification.get("missing_specification_flags") or [])
        trade_confidence = _safe_float(trade_mapping.get("trade_package_mapping_readiness", {}).get("score"), 0.0)

        score = 10.0
        if not description:
            score += 25.0
        if not specification:
            score += 20.0
        if not unit:
            score += 15.0
        if quantity in (None, ""):
            score += 20.0
        if ambiguous_flags:
            score += min(20.0, len(ambiguous_flags) * 5.0)
        if "missing_specification" in missing_flags:
            score += 15.0
        if trade_confidence < 70.0:
            score += 10.0

        risk_score = _clamp(score)
        if risk_score < 25:
            risk_level = "low"
        elif risk_score < 50:
            risk_level = "medium"
        elif risk_score < 75:
            risk_level = "high"
        else:
            risk_level = "extreme"

        risk_flags: List[str] = []
        if not description:
            risk_flags.append("missing_description")
        if not specification:
            risk_flags.append("missing_specification")
        if not unit:
            risk_flags.append("missing_unit_of_measure")
        if quantity in (None, ""):
            risk_flags.append("missing_quantity")
        if ambiguous_flags:
            risk_flags.extend([f"ambiguous:{flag}" for flag in ambiguous_flags])
        if trade_confidence < 70.0:
            risk_flags.append("trade_mapping_low_confidence")

        unresolved_blockers: List[str] = list(classification.get("unresolved_boq_semantic_blockers") or [])
        if risk_score >= 65.0:
            unresolved_blockers.append("measurement_risk_above_threshold")
        if risk_level in {"high", "extreme"}:
            unresolved_blockers.append("measurement_review_required")

        return {
            "analysis_id": f"boq-measurement-risk:{_safe_str(item.get('item_number') or item.get('description') or item.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "item_number": item.get("item_number"),
            "measurement_risk_score": round(risk_score, 2),
            "measurement_risk_level": risk_level,
            "measurement_risk_flags": risk_flags,
            "unresolved_boq_semantic_blockers": unresolved_blockers,
            "measurement_risk_readiness": {
                "ready": risk_score < 35.0,
                "score": round(100.0 - risk_score, 2),
            },
            "warnings": [
                "Measurement risk requires human review" if risk_score >= 50 else "",
            ],
        }

    def score_boq_measurement_risk(self, item: Dict[str, Any], classification: Optional[Dict[str, Any]] = None, trade_mapping: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        analysis = self._score_risk(item, classification=classification, trade_mapping=trade_mapping)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "item_number": analysis["item_number"],
                    "measurement_risk_score": analysis["measurement_risk_score"],
                    "measurement_risk_level": analysis["measurement_risk_level"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_boq_measurement_risk(self) -> Dict[str, Any]:
        latest_item = self._latest_item()
        classification = self.classification_service.classify_boq_item(latest_item, record_history=False)
        trade_mapping = self.trade_mapping_service.map_boq_trade(latest_item, classification=classification, record_history=False)
        analysis = self.score_boq_measurement_risk(latest_item, classification=classification, trade_mapping=trade_mapping, record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["measurement_risk_score"] < 50 else "watch" if analysis["measurement_risk_score"] < 75 else "blocked",
            "measurement_risk_status": analysis["measurement_risk_level"],
            "measurement_risk_score": analysis["measurement_risk_score"],
            "latest_boq_measurement_risk": analysis,
            "boq_measurement_risk_history": history,
            "boq_measurement_risk_history_summary": {
                "analysis_count": len(history),
                "latest_risk_level": analysis["measurement_risk_level"],
            },
            "warnings": analysis["warnings"],
        }

    def boq_measurement_risk_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("measurement_risk_score"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "measurement_risk_status": "low" if score < 25 else "medium" if score < 50 else "high" if score < 75 else ("extreme" if history else "not_found"),
            "measurement_risk_score": score,
            "latest_boq_measurement_risk": latest,
            "boq_measurement_risk_history": history,
            "boq_measurement_risk_history_summary": {
                "analysis_count": len(history),
                "latest_risk_level": latest.get("measurement_risk_level", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


boq_measurement_risk_service = BoqMeasurementRiskService()
