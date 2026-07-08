from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.supplier_intelligence_service import SupplierIntelligenceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "historical-learning-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "supplier_performance_memory_history.json"


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
    seen: List[str] = []
    for value in values:
        text = _safe_str(value)
        if text and text not in seen:
            seen.append(text)
    return seen


class SupplierPerformanceMemoryService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.supplier_intelligence_service = SupplierIntelligenceService(runtime_dir=self.runtime_dir)

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

    def _sample_supplier(self) -> Dict[str, Any]:
        return {
            "supplier_id": "historical-learning-supplier:sample",
            "supplier_name": "Executive Office Solutions",
            "province": "Gauteng",
            "city": "Johannesburg",
            "contact_person": "Bid Desk",
            "email": "bids@example.com",
            "phone": "+27-11-000-0001",
            "delivery_regions": ["All"],
            "products": [{"product_name": "A4 paper", "category": "stationery_office", "unit_price": 72.0, "available_stock": 30000, "lead_time_days": 2}],
        }

    def _sample_tender(self) -> Dict[str, Any]:
        return {
            "rfq_id": "historical-learning-supplier:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "province": "Gauteng",
            "delivery_location": "Gauteng",
            "closing_date": _now_iso(),
        }

    def _build_snapshot(self) -> Dict[str, Any]:
        tender = self._sample_tender()
        supplier = self.supplier_intelligence_service.analyze_supplier_intelligence(self._sample_supplier(), tender=tender, record_history=False)
        history_payload = self.supplier_intelligence_service.supplier_intelligence_history(limit=8)
        supplier_history = history_payload.get("supplier_intelligence_history", []) if isinstance(history_payload, dict) else []
        supplier_score = _safe_float(supplier.get("supplier_intelligence_score"), 0.0)
        compliance = _safe_float(supplier.get("compliance_readiness"), 0.0)
        delivery_risk = _safe_float(supplier.get("delivery_risk_score"), 0.0)
        pricing = _safe_float(supplier.get("pricing_reliability"), 0.0)
        historical = _safe_float(supplier.get("historical_suitability"), 0.0)

        performance_history = [
            {
                "analysis_id": item.get("analysis_id"),
                "generated_at": item.get("generated_at"),
                "supplier_name": item.get("supplier_name"),
                "supplier_intelligence_score": _safe_float(item.get("supplier_intelligence_score"), 0.0),
                "delivery_risk_score": _safe_float(item.get("delivery_risk_score"), 0.0),
                "compliance_readiness": _safe_float(item.get("compliance_readiness"), 0.0),
                "pricing_reliability": _safe_float(item.get("pricing_reliability"), 0.0),
                "recommended_supplier_tier": _safe_str(item.get("recommended_supplier_tier"), "D"),
            }
            for item in supplier_history
            if isinstance(item, dict)
        ]
        performance_average = mean([entry["supplier_intelligence_score"] for entry in performance_history]) if performance_history else supplier_score
        readiness_score = _clamp(mean([supplier_score, compliance, max(0.0, 100.0 - delivery_risk), pricing, historical, 100.0 if performance_history else 55.0]))
        blockers = _unique(list(supplier.get("unresolved_supplier_blockers") or []))
        ready = readiness_score >= 75.0 and not blockers
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        snapshot = {
            "analysis_id": f"supplier-performance-memory:{_safe_str(supplier.get('supplier_id') or supplier.get('supplier_name'), 'sample')}",
            "generated_at": _now_iso(),
            "supplier_name": _safe_str(supplier.get("supplier_name"), "n/a"),
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "supplier_memory_status": status,
            "supplier_memory_score": round(readiness_score, 2),
            "supplier_memory_grade": "ready" if ready else "watch" if status == "watch" else "blocked",
            "supplier_memory_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": blockers},
            "supplier_performance_history": performance_history,
            "supplier_intelligence_outcomes": supplier_history,
            "supplier_performance_summary": {
                "history_count": len(performance_history),
                "average_supplier_score": round(performance_average, 2) if performance_history else round(supplier_score, 2),
                "latest_supplier_score": round(supplier_score, 2),
                "latest_delivery_risk": round(delivery_risk, 2),
            },
            "unresolved_learning_blockers": blockers,
            "autonomous_learning_execution_enabled": False,
            "autonomous_procurement_decision_updates_enabled": False,
            "autonomous_supplier_blacklisting_enabled": False,
            "autonomous_strategy_modification_enabled": False,
            "production_learning_mode_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_learning_review_required": True,
            "executive_feedback_required": True,
            "learning_governance_history": [
                {"event": "supplier_memory_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "supplier_history_reconciled", "status": "passed" if performance_history else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Supplier performance memory is advisory only" if not ready else "",
                "Supplier history is minimal" if not performance_history else "",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def latest_supplier_performance_memory(self) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        history = self._load_history()
        history.append(
            {
                "analysis_id": snapshot["analysis_id"],
                "generated_at": snapshot["generated_at"],
                "supplier_name": snapshot["supplier_name"],
                "supplier_memory_status": snapshot["supplier_memory_status"],
                "supplier_memory_score": snapshot["supplier_memory_score"],
            }
        )
        self._write_history(history)
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_supplier_performance_memory"] = dict(snapshot)
        payload["supplier_performance_memory_history"] = history
        payload["supplier_performance_memory_history_summary"] = {
            "analysis_count": len(history),
            "latest_supplier_name": snapshot["supplier_name"],
            "latest_score": snapshot["supplier_memory_score"],
        }
        return payload

    def list_supplier_performance_memory(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.latest_supplier_performance_memory()
        history = self._load_history()[-max(1, int(limit)) :]
        latest["count"] = len(history)
        latest["supplier_performance_memory_history"] = history
        latest["supplier_performance_memory_history_summary"] = {
            "analysis_count": len(history),
            "latest_supplier_name": latest["supplier_name"],
            "latest_score": latest["supplier_memory_score"],
        }
        return latest

    def supplier_performance_memory_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("supplier_memory_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "supplier_performance_memory_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
