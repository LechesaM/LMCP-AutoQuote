from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "pricing-governance"
POLICY_FILE = DEFAULT_RUNTIME_DIR / "pricing_approval_rules.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "pricing_confidence_history.json"


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


def _load_policy() -> Dict[str, Any]:
    try:
        if POLICY_FILE.exists():
            payload = json.loads(POLICY_FILE.read_text())
            return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}
    return {}


class PricingConfidenceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.policy = _load_policy()

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
            "rfq_id": "pricing-confidence:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "unit_price": 120.0,
            "quantity": 20,
            "unit": "Each",
            "vat_rate": 0.15,
            "markup_rate": 0.25,
        }

    def _latest_item(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_item()

    def _confidence(self, item: Dict[str, Any], benchmark: Optional[Dict[str, Any]] = None, margin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        benchmark = benchmark or {}
        margin = margin or {}
        readiness_scores = [
            100.0 if benchmark.get("pricing_benchmark_readiness", {}).get("ready") else 40.0,
            100.0 if benchmark.get("market_rate_comparison_readiness", {}).get("ready") else 45.0,
            100.0 if benchmark.get("historical_pricing_reference_readiness", {}).get("ready") else 45.0,
            100.0 if benchmark.get("supplier_quote_comparison_readiness", {}).get("ready") else 45.0,
            100.0 if margin.get("margin_scenario_readiness", {}).get("ready") else 50.0,
        ]
        price = _safe_float(item.get("unit_price") or item.get("quoted_unit_price") or item.get("price"), 0.0)
        quantity = _safe_float(item.get("quantity"), 0.0)
        vat_rate = _safe_float(item.get("vat_rate"), 0.15)
        markup_rate = _safe_float(item.get("markup_rate"), 0.25)
        data_completeness = mean([
            100.0 if _safe_str(item.get("title")) else 0.0,
            100.0 if _safe_str(item.get("description")) else 0.0,
            100.0 if price > 0 else 20.0,
            100.0 if quantity > 0 else 30.0,
            100.0 if item.get("unit") else 35.0,
        ])
        confidence_score = _clamp(mean(readiness_scores + [data_completeness, 100.0 - min(40.0, abs(vat_rate - 0.15) * 100.0), 100.0 - min(40.0, abs(markup_rate - 0.25) * 100.0)]))
        blockers: List[str] = []
        if price <= 0:
            blockers.append("missing_price_reference")
        if not benchmark.get("pricing_benchmark_readiness", {}).get("ready"):
            blockers.append("benchmark_readiness_incomplete")
        if not margin.get("margin_scenario_readiness", {}).get("ready"):
            blockers.append("margin_scenario_incomplete")

        return {
            "analysis_id": f"pricing-confidence:{_safe_str(item.get('rfq_id') or item.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "pricing_confidence_score": round(confidence_score, 2),
            "pricing_confidence_ready": confidence_score >= 70.0,
            "pricing_confidence_status": "ready" if confidence_score >= 80.0 else "watch" if confidence_score >= 55.0 else "blocked",
            "pricing_confidence_grade": "ready" if confidence_score >= 80.0 else "watch" if confidence_score >= 55.0 else "blocked",
            "pricing_confidence_readiness": {
                "ready": confidence_score >= 70.0,
                "score": round(confidence_score, 2),
            },
            "pricing_confidence_indicators": {
                "pricing_data_present": price > 0,
                "quantity_present": quantity > 0,
                "vat_visible": vat_rate >= 0.0,
                "markup_visible": markup_rate >= 0.0,
            },
            "unresolved_pricing_blockers": blockers,
            "warnings": [
                "Pricing confidence requires human price approval" if confidence_score < 70.0 or blockers else "",
            ],
        }

    def assess_pricing_confidence(self, item: Dict[str, Any], benchmark: Optional[Dict[str, Any]] = None, margin: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        analysis = self._confidence(item, benchmark=benchmark, margin=margin)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "pricing_confidence_score": analysis["pricing_confidence_score"],
                    "pricing_confidence_status": analysis["pricing_confidence_status"],
                    "pricing_confidence_ready": analysis["pricing_confidence_ready"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_pricing_confidence(self, benchmark: Optional[Dict[str, Any]] = None, margin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        item = self._latest_item()
        analysis = self.assess_pricing_confidence(item, benchmark=benchmark, margin=margin, record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["pricing_confidence_ready"] else "watch",
            "pricing_confidence_status": analysis["pricing_confidence_status"],
            "pricing_confidence_score": analysis["pricing_confidence_score"],
            "latest_pricing_confidence": analysis,
            "pricing_confidence_history": history,
            "pricing_confidence_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": _safe_str(item.get("rfq_id") or item.get("title"), "n/a"),
            },
            "warnings": analysis["warnings"],
        }

    def pricing_confidence_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("pricing_confidence_score"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "pricing_confidence_status": "ready" if score >= 80 else "watch" if score >= 55 else ("blocked" if history else "not_found"),
            "pricing_confidence_score": score,
            "latest_pricing_confidence": latest,
            "pricing_confidence_history": history,
            "pricing_confidence_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": latest.get("analysis_id", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


pricing_confidence_service = PricingConfidenceService()
