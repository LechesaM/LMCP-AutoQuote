from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "pricing-governance"
POLICY_FILE = DEFAULT_RUNTIME_DIR / "pricing_benchmark_policy.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "market_benchmarking_history.json"


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


def _category_from_text(text: str) -> str:
    blob = text.lower()
    mapping = {
        "stationery": ["stationery", "paper", "pen", "file", "folder"],
        "ict": ["computer", "laptop", "server", "network", "router", "switch", "software", "technology"],
        "civil": ["civil", "construction", "road", "paving", "concrete", "brick", "earthworks"],
        "electrical": ["electrical", "cable", "lighting", "switch", "breaker", "wire", "socket"],
        "cleaning": ["cleaning", "detergent", "soap", "hygiene", "sanitiser"],
        "security": ["security", "guard", "cctv", "alarm", "fence"],
    }
    for category, keywords in mapping.items():
        if any(keyword in blob for keyword in keywords):
            return category
    return "general"


class MarketBenchmarkingService:
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
            "rfq_id": "pricing-benchmark:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "unit_price": 120.0,
            "quantity": 20,
            "unit": "Each",
        }

    def _latest_item(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_item()

    def _benchmark(self, item: Dict[str, Any], confidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        confidence = confidence or {}
        text = " ".join([_safe_str(item.get("title")), _safe_str(item.get("description")), _safe_str(item.get("specification"))])
        category = _category_from_text(text)
        policy_defaults = self.policy.get("category_benchmarks", {}) if isinstance(self.policy.get("category_benchmarks"), dict) else {}
        defaults = policy_defaults.get(category, {}) if isinstance(policy_defaults.get(category), dict) else {}
        market_rate = _safe_float(defaults.get("market_rate"), 100.0)
        historical_reference = _safe_float(defaults.get("historical_reference"), market_rate)
        supplier_quote = _safe_float(item.get("unit_price") or item.get("quoted_unit_price") or item.get("price"), 0.0)
        if supplier_quote <= 0:
            supplier_quote = market_rate * 1.02
        variance = round(supplier_quote - market_rate, 2)
        variance_pct = round((variance / market_rate) * 100.0, 2) if market_rate else 0.0
        comparison_ready = confidence.get("pricing_confidence_ready", False) or confidence.get("pricing_confidence_score", 0.0) >= 70.0
        price_spread_threshold = _safe_float((self.policy.get("variance_thresholds") or {}).get("abnormal_pct"), 15.0)
        underpricing_threshold = _safe_float((self.policy.get("variance_thresholds") or {}).get("underpricing_pct"), -12.0)
        overpricing_threshold = _safe_float((self.policy.get("variance_thresholds") or {}).get("overpricing_pct"), 18.0)

        abnormal_variance_indicators = {
            "variance_pct_abnormal": abs(variance_pct) >= price_spread_threshold,
            "variance_pct_high_positive": variance_pct >= overpricing_threshold,
            "variance_pct_high_negative": variance_pct <= underpricing_threshold,
        }
        underpricing_risk_indicators = {
            "underpricing_risk_flag": variance_pct <= underpricing_threshold,
            "pricing_confidence_low": _safe_float(confidence.get("pricing_confidence_score"), 0.0) < 70.0,
            "market_rate_gap": round(market_rate - supplier_quote, 2),
        }
        overpricing_competitiveness_indicators = {
            "competitively_priced": variance_pct <= 5.0,
            "overpriced": variance_pct >= overpricing_threshold,
            "price_position": "competitive" if variance_pct <= 5.0 else "elevated" if variance_pct >= overpricing_threshold else "aligned",
        }
        blockers: List[str] = []
        if not comparison_ready:
            blockers.append("pricing_confidence_not_ready")
        if market_rate <= 0:
            blockers.append("missing_market_rate_reference")
        if supplier_quote <= 0:
            blockers.append("missing_supplier_quote")

        readiness_score = _clamp(mean([
            100.0 if comparison_ready else 55.0,
            100.0 if market_rate > 0 else 45.0,
            100.0 if historical_reference > 0 else 45.0,
            100.0 if supplier_quote > 0 else 45.0,
        ]))

        return {
            "analysis_id": f"market-benchmarking:{_safe_str(item.get('rfq_id') or item.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "benchmark_category": category,
            "market_rate": round(market_rate, 2),
            "historical_reference_rate": round(historical_reference, 2),
            "supplier_quote_rate": round(supplier_quote, 2),
            "price_variance": variance,
            "price_variance_pct": variance_pct,
            "pricing_benchmark_readiness": {
                "ready": readiness_score >= 70.0,
                "score": round(readiness_score, 2),
            },
            "market_rate_comparison_readiness": {
                "ready": market_rate > 0,
                "score": 100.0 if market_rate > 0 else 0.0,
            },
            "historical_pricing_reference_readiness": {
                "ready": historical_reference > 0,
                "score": 100.0 if historical_reference > 0 else 0.0,
            },
            "supplier_quote_comparison_readiness": {
                "ready": supplier_quote > 0,
                "score": 100.0 if supplier_quote > 0 else 0.0,
            },
            "abnormal_price_variance_indicators": abnormal_variance_indicators,
            "underpricing_risk_indicators": underpricing_risk_indicators,
            "overpricing_competitiveness_indicators": overpricing_competitiveness_indicators,
            "vat_visibility": {
                "vat_rate": _safe_float(item.get("vat_rate"), 0.15),
                "vat_amount": round(supplier_quote * _safe_float(item.get("vat_rate"), 0.15), 2),
            },
            "markup_visibility": {
                "markup_rate": _safe_float(item.get("markup_rate"), 0.25),
                "markup_amount": round(supplier_quote * _safe_float(item.get("markup_rate"), 0.25), 2),
            },
            "escalation_required_pricing_items": [
                "price_variance_exceeds_threshold" if abnormal_variance_indicators["variance_pct_abnormal"] else "",
                "underpricing_risk" if underpricing_risk_indicators["underpricing_risk_flag"] else "",
                "overpricing_competitiveness_issue" if overpricing_competitiveness_indicators["overpriced"] else "",
            ],
            "unresolved_pricing_blockers": [blocker for blocker in blockers if blocker],
            "governance_rules": {
                "advisory_only": True,
                "human_price_approval_required": True,
                "automatic_submission_disabled": True,
                "dry_run_enforced": True,
                "supervision_mandatory": True,
            },
            "warnings": [
                "Pricing variance requires human approval" if blockers or abnormal_variance_indicators["variance_pct_abnormal"] else "",
            ],
        }

    def benchmark_market_rates(self, item: Dict[str, Any], confidence: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        analysis = self._benchmark(item, confidence=confidence)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "benchmark_category": analysis["benchmark_category"],
                    "market_rate": analysis["market_rate"],
                    "price_variance_pct": analysis["price_variance_pct"],
                    "pricing_benchmark_readiness": analysis["pricing_benchmark_readiness"]["score"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_market_benchmarking(self, confidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        item = self._latest_item()
        analysis = self.benchmark_market_rates(item, confidence=confidence, record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["pricing_benchmark_readiness"]["ready"] else "watch",
            "market_benchmarking_status": "ready" if analysis["pricing_benchmark_readiness"]["ready"] else "watch",
            "market_benchmarking_score": analysis["pricing_benchmark_readiness"]["score"],
            "latest_market_benchmarking": analysis,
            "market_benchmarking_history": history,
            "market_benchmarking_history_summary": {
                "analysis_count": len(history),
                "latest_category": analysis["benchmark_category"],
            },
            "warnings": analysis["warnings"],
        }

    def market_benchmarking_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("pricing_benchmark_readiness"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "market_benchmarking_status": "ready" if score >= 70 else "watch" if history else "not_found",
            "market_benchmarking_score": score,
            "latest_market_benchmarking": latest,
            "market_benchmarking_history": history,
            "market_benchmarking_history_summary": {
                "analysis_count": len(history),
                "latest_category": latest.get("benchmark_category", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


market_benchmarking_service = MarketBenchmarkingService()
