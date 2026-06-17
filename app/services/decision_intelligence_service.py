from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from app.services.websocket_broker import publish_dashboard_event

DEFAULT_RUNTIME_DIR = Path("runtime")


def _runtime_dir(runtime_dir: Optional[str] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _decision_dir(runtime_dir: Optional[str] = None) -> Path:
    return _runtime_dir(runtime_dir) / "decision_intelligence"


def _decision_history_file(runtime_dir: Optional[str] = None) -> Path:
    return _decision_dir(runtime_dir) / "decision_history.json"


_decision_dir().mkdir(parents=True, exist_ok=True)

BLOCKED_KEYWORDS = {
    "medical": [
        "medical", "pharmaceutical", "medicine", "drug", "clinic", "hospital consumable",
        "syringe", "bandage", "surgical", "gloves", "glucose", "patient", "laboratory reagent",
    ],
    "it": [
        "laptop", "computer", "printer", "server", "monitor", "router", "switch",
        "ups", "software", "licence", "license", "scanner", "tablet", "toner", "ink cartridge",
    ],
    "fuel": ["petrol", "diesel", "fuel", "paraffin"],
    "catering": ["catering", "refreshment", "meal", "food parcel", "beverage", "lunch", "breakfast"],
}

POSITIVE_KEYWORDS = [
    "supply", "delivery", "deliver", "stationery", "cleaning material", "ppe",
    "office furniture", "consumables", "tools", "equipment", "materials", "uniform",
]

BRIEFING_KEYWORDS = [
    "compulsory briefing", "mandatory briefing", "site briefing compulsory",
    "compulsory site meeting", "mandatory site meeting", "briefing session is compulsory",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text_blob(opportunity: Dict[str, Any]) -> str:
    parts = [
        opportunity.get("title"),
        opportunity.get("description"),
        opportunity.get("category"),
        opportunity.get("buyer_name"),
        opportunity.get("organ_of_state"),
        opportunity.get("submission_method"),
        opportunity.get("briefing"),
        opportunity.get("briefing_description"),
    ]
    return " ".join(str(p or "") for p in parts).lower()


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _blocked_category(text: str) -> Optional[str]:
    for category, keywords in BLOCKED_KEYWORDS.items():
        if _contains_any(text, keywords):
            return category
    return None


def score_opportunity(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    text = _text_blob(opportunity)
    score = 50
    reasons: List[str] = []
    blockers: List[str] = []

    buyer_rfq_number = (
        opportunity.get("buyer_rfq_number")
        or opportunity.get("rfq_number")
        or opportunity.get("tender_number")
        or opportunity.get("reference")
        or "RFQ-NO-ID"
    )

    title = opportunity.get("title") or opportunity.get("description") or buyer_rfq_number
    buyer_name = opportunity.get("buyer_name") or opportunity.get("organ_of_state") or opportunity.get("buyer") or "—"

    blocked = _blocked_category(text)
    if blocked:
        blockers.append(f"Blocked category: {blocked}")
        score -= 45

    if _contains_any(text, BRIEFING_KEYWORDS) or opportunity.get("briefing_required") is True:
        blockers.append("Compulsory briefing detected")
        score -= 35

    if _contains_any(text, POSITIVE_KEYWORDS):
        score += 15
        reasons.append("Supply/delivery keywords detected")

    submission_method = str(opportunity.get("submission_method") or "").lower()
    if "email" in submission_method:
        score += 15
        reasons.append("Email submission preferred")
    elif "portal" in submission_method:
        score += 8
        reasons.append("Portal submission acceptable")
    elif "physical" in submission_method or "hand" in submission_method:
        score -= 12
        reasons.append("Physical/manual submission reduces priority")

    estimated_profit = float(opportunity.get("estimated_profit") or opportunity.get("profit") or 0)
    estimated_margin = float(
        opportunity.get("estimated_margin_percent")
        or opportunity.get("margin_percent")
        or opportunity.get("minimum_margin_percent")
        or 0
    )

    if estimated_profit >= 30000:
        score += 20
        reasons.append("Estimated profit meets R30,000 target")
    elif estimated_profit > 0:
        score -= 8
        reasons.append("Estimated profit below R30,000 target")

    if estimated_margin >= 25:
        score += 15
        reasons.append("Margin meets 25% target")
    elif estimated_margin > 0:
        score -= 10
        reasons.append("Margin below 25% target")

    province = str(opportunity.get("province") or "").strip()
    if province:
        score += 3
        reasons.append(f"Province identified: {province}")

    score = max(0, min(100, round(score, 1)))

    if blockers:
        decision = "reject"
    elif score >= 75:
        decision = "auto_approve"
    elif score >= 55:
        decision = "manual_review"
    else:
        decision = "reject"

    if not reasons and not blockers:
        reasons.append("Limited information available; conservative score applied")

    return {
        "buyer_rfq_number": buyer_rfq_number,
        "title": title,
        "buyer_name": buyer_name,
        "score": score,
        "decision": decision,
        "reasons": blockers + reasons,
        "estimated_profit": estimated_profit,
        "estimated_margin_percent": estimated_margin,
        "submission_method": opportunity.get("submission_method") or "",
        "province": province,
        "raw": opportunity,
        "scored_at": _now_iso(),
    }


def load_history(runtime_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    history_file = _decision_history_file(runtime_dir)
    if not history_file.exists():
        return []
    try:
        data = json.loads(history_file.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(items: List[Dict[str, Any]], runtime_dir: Optional[str] = None) -> None:
    history_file = _decision_history_file(runtime_dir)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(items[-500:], indent=2, default=str))


async def score_and_publish(
    opportunity: Dict[str, Any],
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    scored = score_opportunity(opportunity)

    history = load_history(runtime_dir=runtime_dir)
    history.append(scored)
    save_history(history, runtime_dir=runtime_dir)

    event_type = "decision_scored"
    if scored["decision"] == "auto_approve":
        event_type = "opportunity_auto_approved"
    elif scored["decision"] == "manual_review":
        event_type = "opportunity_manual_review"
    elif scored["decision"] == "reject":
        event_type = "opportunity_rejected"

    await publish_dashboard_event(
        event_type=event_type,
        payload=scored,
        source="decision-intelligence",
    )

    return scored


async def score_many_and_publish(
    opportunities: List[Dict[str, Any]],
    runtime_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    results = []
    for opportunity in opportunities:
        results.append(await score_and_publish(opportunity, runtime_dir=runtime_dir))
    return results


def get_decision_summary(limit: int = 20, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    history = load_history(runtime_dir=runtime_dir)
    recent = list(reversed(history[-limit:]))

    total = len(history)
    auto = len([x for x in history if x.get("decision") == "auto_approve"])
    manual = len([x for x in history if x.get("decision") == "manual_review"])
    rejected = len([x for x in history if x.get("decision") == "reject"])
    scores = [float(x.get("score") or 0) for x in history]

    top = sorted(
        [x for x in history if x.get("decision") in {"auto_approve", "manual_review"}],
        key=lambda x: float(x.get("score") or 0),
        reverse=True,
    )[:10]

    recent_rejections = [x for x in reversed(history) if x.get("decision") == "reject"][:10]

    return {
        "status": "ok",
        "summary": {
            "total_scored": total,
            "auto_approved": auto,
            "manual_review": manual,
            "rejected": rejected,
            "average_score": round(mean(scores), 1) if scores else 0,
        },
        "top_opportunities": top,
        "recent_rejections": recent_rejections,
        "recent_decisions": recent,
        "history_file": str(_decision_history_file(runtime_dir)),
        "updated_at": _now_iso(),
    }
