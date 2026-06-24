from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.boq_item_classification_service import BoqItemClassificationService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "boq-semantic-understanding"
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "boq_trade_mapping_history.json"


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


def _infer_trade(blob: str) -> Dict[str, str]:
    for trade, keywords in TRADE_KEYWORDS.items():
        if any(keyword in blob for keyword in keywords):
            return {
                "trade_category": trade,
                "package_category": "works" if trade in {"civil", "electrical", "plumbing"} else "services" if trade == "professional_services" else "goods",
            }
    return {"trade_category": "general_goods", "package_category": "goods"}


class BoqTradeMappingService:
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

    def _map_item(self, item: Dict[str, Any], classification: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        classification = classification or self.classification_service.classify_boq_item(item, record_history=False)
        blob = " ".join(
            str(value or "")
            for value in (
                item.get("description"),
                item.get("specification"),
                item.get("title"),
                classification.get("trade_package_category"),
                classification.get("package_category"),
            )
        ).lower()
        mapped = _infer_trade(blob)
        if classification.get("trade_package_category") and classification.get("trade_package_category") != "general_goods":
            mapped = {
                "trade_category": str(classification.get("trade_package_category")),
                "package_category": str(classification.get("package_category") or "goods"),
            }

        confidence = 95.0 if mapped["trade_category"] != "general_goods" else 65.0
        readiness = _clamp((confidence + _safe_float(classification.get("classification_score"), 0.0)) / 2.0)
        blockers: List[str] = list(classification.get("unresolved_boq_semantic_blockers") or [])
        if readiness < 70.0:
            blockers.append("trade_package_mapping_below_threshold")

        return {
            "analysis_id": f"boq-trade-mapping:{_safe_str(item.get('item_number') or item.get('description') or item.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "item_number": item.get("item_number"),
            "trade_package_category": mapped["trade_category"],
            "package_category": mapped["package_category"],
            "trade_package_mapping_readiness": {
                "ready": readiness >= 70.0,
                "score": round(readiness, 2),
            },
            "trade_mapping_confidence": round(confidence, 2),
            "unresolved_boq_semantic_blockers": blockers,
            "warnings": [
                "Trade/package mapping needs review" if readiness < 70.0 else "",
            ],
        }

    def map_boq_trade(self, item: Dict[str, Any], classification: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        analysis = self._map_item(item, classification=classification)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "item_number": analysis["item_number"],
                    "trade_package_category": analysis["trade_package_category"],
                    "package_category": analysis["package_category"],
                    "trade_package_mapping_readiness": analysis["trade_package_mapping_readiness"]["score"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_boq_trade_mapping(self) -> Dict[str, Any]:
        classification = self.classification_service.classify_boq_item(self._latest_item(), record_history=False)
        analysis = self.map_boq_trade(self._latest_item(), classification=classification, record_history=True)
        history = self._load_history()
        status = "ok" if analysis["trade_package_mapping_readiness"]["ready"] else "watch"
        return {
            "status": status,
            "trade_package_mapping_status": "ready" if analysis["trade_package_mapping_readiness"]["ready"] else "watch",
            "trade_package_mapping_score": analysis["trade_package_mapping_readiness"]["score"],
            "latest_boq_trade_mapping": analysis,
            "boq_trade_mapping_history": history,
            "boq_trade_mapping_history_summary": {
                "analysis_count": len(history),
                "latest_trade_package_category": analysis["trade_package_category"],
            },
            "warnings": analysis["warnings"],
        }

    def boq_trade_mapping_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("trade_package_mapping_readiness"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "trade_package_mapping_status": "ready" if score >= 70 else "watch" if history else "not_found",
            "trade_package_mapping_score": score,
            "latest_boq_trade_mapping": latest,
            "boq_trade_mapping_history": history,
            "boq_trade_mapping_history_summary": {
                "analysis_count": len(history),
                "latest_trade_package_category": latest.get("trade_package_category", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


boq_trade_mapping_service = BoqTradeMappingService()
