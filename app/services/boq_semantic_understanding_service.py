from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.boq_ambiguity_detection_service import BoqAmbiguityDetectionService
from app.services.boq_item_classification_service import BoqItemClassificationService
from app.services.boq_measurement_risk_service import BoqMeasurementRiskService
from app.services.boq_trade_mapping_service import BoqTradeMappingService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "boq-semantic-understanding"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "boq_semantic_understanding_history.json"


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


def _extract_rows(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in ("boq_rows", "normalized_boq_rows", "pricing_ready_rows", "review_rows", "items", "line_items", "rows"):
        value = record.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    rows.append(entry)
    return rows or [record]


class BoqSemanticUnderstandingService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = BoqItemClassificationService(runtime_dir=self.runtime_dir)
        self.trade_mapping_service = BoqTradeMappingService(runtime_dir=self.runtime_dir)
        self.measurement_risk_service = BoqMeasurementRiskService(runtime_dir=self.runtime_dir)
        self.ambiguity_detection_service = BoqAmbiguityDetectionService(runtime_dir=self.runtime_dir)

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

    def _sample_record(self) -> Dict[str, Any]:
        return {
            "rfq_id": "boq-semantic-understanding:sample",
            "title": "Supply and install electrical fittings",
            "boq_rows": [
                {"item_number": 1, "description": "LED light fitting", "specification": "1200mm fitting", "unit": "Each", "quantity": 10},
                {"item_number": 2, "description": "Cable ducting", "specification": "PVC trunking", "unit": "m", "quantity": 50},
            ],
        }

    def _latest_record(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_record()

    def _row_analysis(self, row: Dict[str, Any]) -> Dict[str, Any]:
        classification = self.classification_service.classify_boq_item(row, record_history=False)
        trade_mapping = self.trade_mapping_service.map_boq_trade(row, classification=classification, record_history=False)
        measurement = self.measurement_risk_service.score_boq_measurement_risk(row, classification=classification, trade_mapping=trade_mapping, record_history=False)
        ambiguity = self.ambiguity_detection_service.detect_boq_ambiguity(row, classification=classification, record_history=False)

        classification_score = _safe_float(classification.get("classification_score"), 0.0)
        trade_score = _safe_float(trade_mapping.get("trade_package_mapping_readiness", {}).get("score"), 0.0)
        uom_score = _safe_float(classification.get("unit_of_measure_normalization_readiness", {}).get("score"), 0.0)
        quantity_score = _safe_float(classification.get("quantity_interpretation_readiness", {}).get("score"), 0.0)
        pricing_score = _safe_float(classification.get("pricing_preparation_readiness", {}).get("score"), 0.0)
        risk_score = _safe_float(measurement.get("measurement_risk_score"), 0.0)
        ambiguity_score = _safe_float(ambiguity.get("ambiguity_score"), 0.0)

        semantic_score = _clamp(mean([classification_score, trade_score, uom_score, quantity_score, pricing_score, max(0.0, 100.0 - risk_score), max(0.0, 100.0 - ambiguity_score)]))
        row_status = "ready" if semantic_score >= 80 and not measurement.get("unresolved_boq_semantic_blockers") and not ambiguity.get("ambiguous_item_flags") else "needs_review" if semantic_score >= 55 else "blocked"

        unresolved_blockers = _unique(
            list(classification.get("unresolved_boq_semantic_blockers") or [])
            + list(trade_mapping.get("unresolved_boq_semantic_blockers") or [])
            + list(measurement.get("unresolved_boq_semantic_blockers") or [])
            + [f"ambiguous:{flag}" for flag in (ambiguity.get("ambiguous_item_flags") or [])]
            + [f"missing:{flag}" for flag in (ambiguity.get("missing_specification_flags") or [])]
        )

        return {
            "analysis_id": f"boq-semantic:{_safe_str(row.get('item_number') or row.get('description') or row.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "item_number": row.get("item_number"),
            "description": classification.get("description"),
            "specification": classification.get("specification"),
            "unit": classification.get("unit"),
            "quantity": classification.get("quantity"),
            "trade_package_category": trade_mapping.get("trade_package_category"),
            "package_category": trade_mapping.get("package_category"),
            "boq_item_classification_readiness": classification.get("boq_item_classification_readiness"),
            "trade_package_mapping_readiness": trade_mapping.get("trade_package_mapping_readiness"),
            "unit_of_measure_normalization_readiness": classification.get("unit_of_measure_normalization_readiness"),
            "quantity_interpretation_readiness": classification.get("quantity_interpretation_readiness"),
            "measurement_risk_score": measurement.get("measurement_risk_score"),
            "ambiguous_item_flags": ambiguity.get("ambiguous_item_flags") or [],
            "missing_specification_flags": ambiguity.get("missing_specification_flags") or [],
            "pricing_preparation_readiness": classification.get("pricing_preparation_readiness"),
            "unresolved_boq_semantic_blockers": unresolved_blockers,
            "semantic_score": round(semantic_score, 2),
            "semantic_status": row_status,
            "semantic_grade": "ready" if row_status == "ready" else "watch" if row_status == "needs_review" else "blocked",
        }

    def _analyze_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        rows = _extract_rows(record)
        row_analyses = [self._row_analysis(row) for row in rows]
        classification_score = _clamp(mean([_safe_float(row["boq_item_classification_readiness"]["score"], 0.0) for row in row_analyses])) if row_analyses else 0.0
        trade_score = _clamp(mean([_safe_float(row["trade_package_mapping_readiness"]["score"], 0.0) for row in row_analyses])) if row_analyses else 0.0
        uom_score = _clamp(mean([_safe_float(row["unit_of_measure_normalization_readiness"]["score"], 0.0) for row in row_analyses])) if row_analyses else 0.0
        quantity_score = _clamp(mean([_safe_float(row["quantity_interpretation_readiness"]["score"], 0.0) for row in row_analyses])) if row_analyses else 0.0
        pricing_score = _clamp(mean([_safe_float(row["pricing_preparation_readiness"]["score"], 0.0) for row in row_analyses])) if row_analyses else 0.0
        measurement_risk_score = _clamp(max([_safe_float(row["measurement_risk_score"], 0.0) for row in row_analyses] or [0.0]))

        ambiguous_item_flags = _unique([flag for row in row_analyses for flag in row.get("ambiguous_item_flags", [])])
        missing_specification_flags = _unique([flag for row in row_analyses for flag in row.get("missing_specification_flags", [])])
        unresolved_blockers = _unique([flag for row in row_analyses for flag in row.get("unresolved_boq_semantic_blockers", [])])

        semantic_score = _clamp(mean([classification_score, trade_score, uom_score, quantity_score, pricing_score, max(0.0, 100.0 - measurement_risk_score), max(0.0, 100.0 - len(ambiguous_item_flags) * 12.0)]))
        if semantic_score >= 80 and not unresolved_blockers:
            status = "ok"
        elif semantic_score >= 55:
            status = "watch"
        else:
            status = "blocked"

        return {
            "analysis_id": f"boq-semantic-understanding:{_safe_str(record.get('rfq_id') or record.get('title') or record.get('buyer_name'), 'sample')}",
            "generated_at": _now_iso(),
            "rfq_id": _safe_str(record.get("rfq_id") or record.get("rfq_reference"), "n/a"),
            "title": _safe_str(record.get("title"), "n/a"),
            "boq_row_count": len(row_analyses),
            "boq_item_classification_readiness": {
                "ready": classification_score >= 70.0,
                "score": round(classification_score, 2),
            },
            "trade_package_mapping_readiness": {
                "ready": trade_score >= 70.0,
                "score": round(trade_score, 2),
            },
            "unit_of_measure_normalization_readiness": {
                "ready": uom_score >= 70.0,
                "score": round(uom_score, 2),
            },
            "quantity_interpretation_readiness": {
                "ready": quantity_score >= 70.0,
                "score": round(quantity_score, 2),
            },
            "measurement_risk_score": round(measurement_risk_score, 2),
            "ambiguous_item_flags": ambiguous_item_flags,
            "missing_specification_flags": missing_specification_flags,
            "pricing_preparation_readiness": {
                "ready": pricing_score >= 70.0 and not unresolved_blockers,
                "score": round(pricing_score, 2),
            },
            "unresolved_boq_semantic_blockers": unresolved_blockers,
            "boq_row_analyses": row_analyses,
            "boq_semantic_understanding_status": status,
            "boq_semantic_understanding_score": round(semantic_score, 2),
            "boq_semantic_understanding_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
            "what_this_unlocks": [
                "BOQ item classification",
                "trade/package mapping",
                "unit-of-measure normalization",
                "quantity interpretation",
                "measurement risk detection",
                "ambiguous item detection",
                "pricing preparation intelligence",
            ],
            "warnings": [
                "BOQ semantic understanding remains blocked by unresolved semantic blockers" if unresolved_blockers else "",
                "Ambiguous BOQ descriptions require human supervision" if ambiguous_item_flags else "",
            ],
            "recovery_rationale": {
                "summary": "BOQ semantic readiness is derived from classification, mapping, measurement risk, and ambiguity signals.",
                "score_impact": {
                    "base_score": round(mean([classification_score, trade_score, uom_score, quantity_score, pricing_score]), 2) if row_analyses else 0.0,
                    "risk_penalty": round(measurement_risk_score, 2),
                    "ambiguity_penalty": round(len(ambiguous_item_flags) * 12.0, 2),
                    "final_score": round(semantic_score, 2),
                },
            },
        }

    def analyze_boq_semantics(self, item: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        analysis = self._analyze_record(item)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "rfq_id": analysis["rfq_id"],
                    "title": analysis["title"],
                    "boq_semantic_understanding_status": analysis["boq_semantic_understanding_status"],
                    "boq_semantic_understanding_score": analysis["boq_semantic_understanding_score"],
                    "boq_row_count": analysis["boq_row_count"],
                    "measurement_risk_score": analysis["measurement_risk_score"],
                    "unresolved_boq_semantic_blockers": analysis["unresolved_boq_semantic_blockers"],
                }
            )
            self._write_history(history)
        return analysis

    def list_boq_semantic_understanding(self, limit: int = 20) -> Dict[str, Any]:
        record = self._latest_record()
        analysis = self.analyze_boq_semantics(record, record_history=True)
        history = self._load_history()
        status = analysis["boq_semantic_understanding_status"]
        return {
            "status": "ok" if status == "ok" else "watch" if status == "watch" else "blocked",
            "boq_semantic_understanding_status": status,
            "boq_semantic_understanding_score": analysis["boq_semantic_understanding_score"],
            "boq_semantic_understanding_grade": analysis["boq_semantic_understanding_grade"],
            "latest_boq_semantic_understanding": analysis,
            "boq_semantic_understanding_history": history[-max(1, int(limit)) :],
            "boq_semantic_understanding_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": analysis["rfq_id"],
                "latest_title": analysis["title"],
            },
            "boq_item_classification_readiness": analysis["boq_item_classification_readiness"],
            "trade_package_mapping_readiness": analysis["trade_package_mapping_readiness"],
            "unit_of_measure_normalization_readiness": analysis["unit_of_measure_normalization_readiness"],
            "quantity_interpretation_readiness": analysis["quantity_interpretation_readiness"],
            "measurement_risk_score": analysis["measurement_risk_score"],
            "ambiguous_item_flags": analysis["ambiguous_item_flags"],
            "missing_specification_flags": analysis["missing_specification_flags"],
            "pricing_preparation_readiness": analysis["pricing_preparation_readiness"],
            "unresolved_boq_semantic_blockers": analysis["unresolved_boq_semantic_blockers"],
            "boq_row_analyses": analysis["boq_row_analyses"],
            "what_this_unlocks": analysis["what_this_unlocks"],
            "warnings": analysis["warnings"],
        }

    def latest_boq_semantic_understanding(self) -> Dict[str, Any]:
        return self.list_boq_semantic_understanding(limit=20)

    def boq_semantic_understanding_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("boq_semantic_understanding_score"), 0.0) if history else 0.0
        status = "ok" if score >= 80 else "watch" if score >= 55 else ("blocked" if history else "not_found")
        return {
            "status": "ok",
            "count": len(history),
            "boq_semantic_understanding_status": status,
            "boq_semantic_understanding_score": score,
            "latest_boq_semantic_understanding": latest,
            "boq_semantic_understanding_history": history,
            "boq_semantic_understanding_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": latest.get("rfq_id", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


boq_semantic_understanding_service = BoqSemanticUnderstandingService()
