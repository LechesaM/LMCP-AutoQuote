import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.buyer_event import BuyerEvent
from app.models.buyer_profile import BuyerProfile
from app.models.procurement_signal import ProcurementSignal
from app.services.procurement_intelligence.normalizer import (
    normalize_category,
    normalize_notice_type,
)
from app.services.procurement_intelligence.buyer_identity import identify_buyer
from app.services.procurement_intelligence.buyer_profiler import build_profile_summary
from app.services.procurement_intelligence.behavior_engine import analyze_buyer_behavior
from app.services.procurement_intelligence.signal_engine import generate_procurement_signals
from app.services.procurement_intelligence.intelligence_score import calculate_intelligence_score


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        cleaned = cleaned.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(cleaned)
        except Exception:
            pass

        patterns = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ]
        for pattern in patterns:
            try:
                return datetime.strptime(cleaned, pattern)
            except Exception:
                continue

    return None


def _serialize_opportunity(opportunity: Any) -> Dict[str, Any]:
    return {
        "buyer_name": _get_attr(opportunity, "buyer_name")
        or _get_attr(opportunity, "department")
        or _get_attr(opportunity, "entity")
        or _get_attr(opportunity, "issuer")
        or _get_attr(opportunity, "organization"),
        "title": _get_attr(opportunity, "title"),
        "description": _get_attr(opportunity, "description"),
        "province": _get_attr(opportunity, "province"),
        "portal_source": _get_attr(opportunity, "source")
        or _get_attr(opportunity, "portal_source")
        or _get_attr(opportunity, "portal"),
        "published_at": _get_attr(opportunity, "published_at")
        or _get_attr(opportunity, "date_published")
        or _get_attr(opportunity, "published_date"),
        "closing_at": _get_attr(opportunity, "closing_at")
        or _get_attr(opportunity, "closing_date")
        or _get_attr(opportunity, "deadline"),
        "notice_type": _get_attr(opportunity, "notice_type"),
        "relevance_score": _get_attr(opportunity, "relevance_score", 60.0),
        "source_url": _get_attr(opportunity, "source_url")
        or _get_attr(opportunity, "url")
        or _get_attr(opportunity, "link"),
        "estimated_value": _get_attr(opportunity, "estimated_value"),
        "currency": _get_attr(opportunity, "currency", "ZAR"),
    }


def _build_source_hash(payload: Dict[str, Any], buyer_code: str, category: str) -> str:
    raw = "||".join(
        [
            str(buyer_code or ""),
            str(payload.get("title") or ""),
            str(payload.get("source_url") or ""),
            str(payload.get("published_at") or ""),
            str(category or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fetch_historical_events(db: Any, buyer_code: str) -> List[Dict[str, Any]]:
    rows = (
        db.query(BuyerEvent)
        .filter(BuyerEvent.buyer_code == buyer_code)
        .order_by(BuyerEvent.published_at.asc(), BuyerEvent.id.asc())
        .all()
    )

    events: List[Dict[str, Any]] = []
    for row in rows:
        events.append(
            {
                "buyer_code": row.buyer_code,
                "buyer_name": row.buyer_name_normalized,
                "province": row.province,
                "portal_source": row.portal_source,
                "buyer_type": row.buyer_type,
                "title": row.title,
                "description": row.description,
                "category": row.category,
                "notice_type": row.notice_type,
                "published_at": row.published_at,
                "closing_at": row.closing_at,
            }
        )
    return events


def _save_buyer_event(
    db: Any,
    payload: Dict[str, Any],
    buyer_info: Dict[str, Any],
    category: str,
    notice_type: str,
) -> BuyerEvent:
    source_hash = _build_source_hash(payload, buyer_info["buyer_code"], category)

    existing = (
        db.query(BuyerEvent)
        .filter(BuyerEvent.source_hash == source_hash)
        .first()
    )
    if existing:
        return existing

    event = BuyerEvent(
        buyer_code=buyer_info["buyer_code"],
        buyer_name_raw=payload.get("buyer_name"),
        buyer_name_normalized=buyer_info["buyer_name"],
        buyer_type=buyer_info["buyer_type"],
        province=buyer_info["province"],
        portal_source=buyer_info["portal_source"],
        title=payload.get("title") or "Untitled Opportunity",
        description=payload.get("description"),
        category=category,
        subcategory=None,
        notice_type=notice_type,
        published_at=_parse_datetime(payload.get("published_at")),
        closing_at=_parse_datetime(payload.get("closing_at")),
        estimated_value=payload.get("estimated_value"),
        currency=payload.get("currency") or "ZAR",
        source_url=payload.get("source_url"),
        source_hash=source_hash,
    )

    db.add(event)
    db.flush()
    return event


def _save_or_update_buyer_profile(
    db: Any,
    buyer_info: Dict[str, Any],
    profile_summary: Dict[str, Any],
    signals: List[Dict[str, Any]],
) -> BuyerProfile:
    profile = (
        db.query(BuyerProfile)
        .filter(BuyerProfile.buyer_code == buyer_info["buyer_code"])
        .first()
    )

    predicted_window = None
    if signals:
        first_signal = signals[0]
        predicted_window = {
            "predicted_start_date": first_signal.get("predicted_start_date"),
            "predicted_end_date": first_signal.get("predicted_end_date"),
        }

    if profile is None:
        profile = BuyerProfile(
            buyer_code=buyer_info["buyer_code"],
            buyer_name=buyer_info["buyer_name"],
            buyer_type=buyer_info["buyer_type"],
            province=buyer_info["province"],
        )
        db.add(profile)

    profile.buyer_name = buyer_info["buyer_name"]
    profile.buyer_type = buyer_info["buyer_type"]
    profile.province = buyer_info["province"]
    profile.event_count = int(profile_summary.get("event_count") or 0)
    profile.first_seen_at = _parse_datetime(profile_summary.get("first_seen_at"))
    profile.last_seen_at = _parse_datetime(profile_summary.get("last_seen_at"))
    profile.avg_days_between_buys = profile_summary.get("avg_days_between_buys")
    profile.top_categories_json = json.dumps(profile_summary.get("top_categories", []))
    profile.predicted_next_buy_window_json = json.dumps(predicted_window) if predicted_window else None
    profile.procurement_frequency_score = float(profile_summary.get("procurement_frequency_score") or 0.0)
    profile.repeat_buying_score = float(profile_summary.get("repeat_buying_score") or 0.0)
    profile.buyer_activity_score = float(profile_summary.get("buyer_activity_score") or 0.0)

    db.flush()
    return profile


def _save_signals(
    db: Any,
    buyer_code: str,
    current_category: str,
    signals: List[Dict[str, Any]],
    source_event_count: int,
) -> None:
    if not signals:
        return

    db.query(ProcurementSignal).filter(
        ProcurementSignal.buyer_code == buyer_code,
        ProcurementSignal.category == current_category,
    ).delete(synchronize_session=False)

    for signal in signals:
        signal_row = ProcurementSignal(
            buyer_code=buyer_code,
            signal_type=signal.get("signal_type") or "unknown_signal",
            category=signal.get("category") or current_category,
            confidence_score=float(signal.get("confidence_score") or 0.0),
            reason=signal.get("reason"),
            predicted_start_date=(
                datetime.fromisoformat(signal["predicted_start_date"]).date()
                if signal.get("predicted_start_date")
                else None
            ),
            predicted_end_date=(
                datetime.fromisoformat(signal["predicted_end_date"]).date()
                if signal.get("predicted_end_date")
                else None
            ),
            source_event_count=source_event_count,
        )
        db.add(signal_row)

    db.flush()


def process_buyer_intelligence(db: Any, opportunity: Any) -> Dict[str, Any]:
    payload = _serialize_opportunity(opportunity)

    buyer_info = identify_buyer(
        buyer_name=payload["buyer_name"],
        province=payload["province"],
        portal_source=payload["portal_source"],
    )

    current_category = normalize_category(
        payload.get("title"),
        payload.get("description"),
    )
    current_notice_type = normalize_notice_type(
        payload.get("notice_type"),
        payload.get("title"),
    )

    _save_buyer_event(
        db=db,
        payload=payload,
        buyer_info=buyer_info,
        category=current_category,
        notice_type=current_notice_type,
    )

    historical_events = _fetch_historical_events(db, buyer_info["buyer_code"])

    profile_summary = build_profile_summary(historical_events)
    behavior_summary = analyze_buyer_behavior(
        current_category=current_category,
        profile_summary=profile_summary,
        historical_events=historical_events,
    )
    signals = generate_procurement_signals(
        buyer_code=buyer_info["buyer_code"],
        current_category=current_category,
        profile_summary=profile_summary,
        behavior_summary=behavior_summary,
    )
    score_summary = calculate_intelligence_score(
        base_relevance_score=float(payload.get("relevance_score") or 60.0),
        profile_summary=profile_summary,
        behavior_summary=behavior_summary,
        signals=signals,
    )

    _save_or_update_buyer_profile(
        db=db,
        buyer_info=buyer_info,
        profile_summary=profile_summary,
        signals=signals,
    )

    _save_signals(
        db=db,
        buyer_code=buyer_info["buyer_code"],
        current_category=current_category,
        signals=signals,
        source_event_count=int(profile_summary.get("event_count") or 0),
    )

    return {
        "buyer_code": buyer_info["buyer_code"],
        "buyer_name": buyer_info["buyer_name"],
        "buyer_type": buyer_info["buyer_type"],
        "province": buyer_info["province"],
        "category": current_category,
        "notice_type": current_notice_type,
        "profile_summary": profile_summary,
        "behavior_summary": behavior_summary,
        "signals": signals,
        "buyer_activity_score": score_summary["buyer_activity_score"],
        "repeat_buying_score": score_summary["repeat_buying_score"],
        "signal_confidence_score": score_summary["signal_confidence_score"],
        "intelligence_score": score_summary["intelligence_score"],
        "quote_ready": score_summary["quote_ready"],
    }
