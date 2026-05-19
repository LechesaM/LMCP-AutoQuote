from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def assess_quote_aging(payload: Dict[str, Any], *, reference_date: datetime | None = None) -> Dict[str, Any]:
    data = dict(payload or {})
    reference_date = reference_date or datetime.now(timezone.utc)
    received = _parse_dt(data.get("quote_received_date") or data.get("received_date"))
    valid_until = _parse_dt(data.get("quote_valid_until") or data.get("valid_until"))
    source_type = str(data.get("quotation_source_type") or data.get("source_type") or "").strip().lower()

    age_days = 0
    if received:
        age_days = max(0, (reference_date - received).days)
    days_until_expiry = None
    if valid_until:
        days_until_expiry = (valid_until - reference_date).days

    stale_pricing_warnings = []
    if valid_until and days_until_expiry is not None and days_until_expiry < 0:
        stale_pricing_warnings.append("expired quote")
    elif age_days >= 60:
        stale_pricing_warnings.append("old pricing")
    elif age_days >= 30:
        stale_pricing_warnings.append("stale pricing warning")
    if source_type.startswith("historical"):
        stale_pricing_warnings.append("historical pricing advisory-only")

    if valid_until and days_until_expiry is not None and days_until_expiry < 0:
        aging_severity = "high"
        risk_level = "HIGH_RISK"
        quote_expiry_risk = "expired"
    elif age_days >= 60 or (days_until_expiry is not None and days_until_expiry <= 3):
        aging_severity = "high"
        risk_level = "HIGH_RISK"
        quote_expiry_risk = "near expiry"
    elif age_days >= 30:
        aging_severity = "medium"
        risk_level = "medium"
        quote_expiry_risk = "stale"
    else:
        aging_severity = "low"
        risk_level = "low"
        quote_expiry_risk = "fresh"

    return {
        "quote_age_days": age_days,
        "days_until_expiry": days_until_expiry,
        "quote_expiry_risk": quote_expiry_risk,
        "stale_pricing_warnings": stale_pricing_warnings,
        "aging_severity": aging_severity,
        "risk_level": risk_level,
        "historical_pricing_advisory": source_type.startswith("historical"),
        "advisory_only": True,
    }
