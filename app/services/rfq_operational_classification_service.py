from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo


BUSINESS_TIMEZONE = ZoneInfo("Africa/Johannesburg")
CLASSIFICATION_VERSION = "rfq_operational_classification_v1"


class RfqOperationalClassification(str, Enum):
    ACTIVE = "ACTIVE"
    HISTORICAL = "HISTORICAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class HistoricalReason(str, Enum):
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"
    AWARDED = "AWARDED"
    CANCELLED = "CANCELLED"
    WITHDRAWN = "WITHDRAWN"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"
    HISTORICAL_NOTICE = "HISTORICAL_NOTICE"
    TEST_RFQ = "TEST_RFQ"
    ARCHIVED_SUBMISSION = "ARCHIVED_SUBMISSION"
    MANUAL_ARCHIVE = "MANUAL_ARCHIVE"


class ReviewReason(str, Enum):
    MISSING_CLOSING_DATE = "MISSING_CLOSING_DATE"
    INVALID_CLOSING_DATE = "INVALID_CLOSING_DATE"
    AMBIGUOUS_STATUS = "AMBIGUOUS_STATUS"
    CONFLICTING_LIFECYCLE_DATA = "CONFLICTING_LIFECYCLE_DATA"
    UNKNOWN_RECORD_TYPE = "UNKNOWN_RECORD_TYPE"
    INSUFFICIENT_DATE_PRECISION = "INSUFFICIENT_DATE_PRECISION"
    UNKNOWN_TIMEZONE = "UNKNOWN_TIMEZONE"


@dataclass(frozen=True)
class RfqClassificationResult:
    classification: RfqOperationalClassification
    reason: str
    normalized_status: Optional[str]
    normalized_closing_at: Optional[datetime]
    confidence: float

    def to_dict(self) -> dict:
        return {
            "classification": self.classification.value,
            "reason": self.reason,
            "normalized_status": self.normalized_status,
            "normalized_closing_at": self.normalized_closing_at.isoformat() if self.normalized_closing_at else None,
            "confidence": self.confidence,
            "classification_version": CLASSIFICATION_VERSION,
        }


def canonical_rfq_id(rfq: Mapping[str, Any]) -> str:
    for key in (
        "rfq_id",
        "canonical_rfq_id",
        "rfq_number",
        "buyer_rfq_number",
        "reference_number",
        "source_reference",
        "tender_No",
        "tender_number",
        "id",
    ):
        value = str(rfq.get(key) or "").strip()
        if value:
            return value
    title = str(rfq.get("title") or rfq.get("description") or "").strip()
    buyer = str(rfq.get("buyer_name") or rfq.get("buyer") or "").strip()
    return re.sub(r"[^A-Za-z0-9._-]+", "-", f"{buyer}-{title}".strip()).strip("-")[:120] or "UNKNOWN_RFQ"


def _first_text(rfq: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = rfq.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_status(rfq: Mapping[str, Any]) -> Tuple[Optional[str], str]:
    raw = _first_text(
        rfq,
        "operational_status",
        "status",
        "raw_status",
        "current_state",
        "lifecycle_state",
        "pipeline_status",
        "submission_status",
        "record_type",
        "notice_type",
    )
    blob = " ".join(
        str(rfq.get(key) or "")
        for key in (
            "status",
            "raw_status",
            "current_state",
            "lifecycle_state",
            "pipeline_status",
            "submission_status",
            "record_type",
            "notice_type",
            "title",
            "description",
            "source",
        )
    ).lower()
    if not raw and not blob.strip():
        return None, ""
    normalized = raw.strip().upper().replace("-", "_").replace(" ", "_") if raw else ""
    return normalized or None, blob


def _parse_closing(value: Any) -> Tuple[Optional[datetime], Optional[str]]:
    if value is None:
        return None, ReviewReason.MISSING_CLOSING_DATE.value
    raw = str(value).strip()
    if not raw:
        return None, ReviewReason.MISSING_CLOSING_DATE.value
    lowered = raw.lower()
    if lowered in {"unknown", "n/a", "na", "tbc", "tba", "none", "null"}:
        return None, ReviewReason.MISSING_CLOSING_DATE.value
    if re.fullmatch(r"\d{4}", raw):
        return None, ReviewReason.INSUFFICIENT_DATE_PRECISION.value
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        return None, ReviewReason.INSUFFICIENT_DATE_PRECISION.value

    candidate = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except Exception:
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except Exception:
                parsed = None  # type: ignore[assignment]
        if parsed is None:
            return None, ReviewReason.INVALID_CLOSING_DATE.value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BUSINESS_TIMEZONE)
    if parsed.timetz().replace(tzinfo=None) == time(0, 0) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed.astimezone(timezone.utc), None


def _closing_value(rfq: Mapping[str, Any]) -> Any:
    for key in (
        "closing_at",
        "closing_date",
        "closing",
        "close_date",
        "deadline",
        "submission_deadline",
        "bid_closing_date",
        "tender_closing_date",
    ):
        if rfq.get(key) not in (None, ""):
            return rfq.get(key)
    source_payload = rfq.get("source_payload")
    if isinstance(source_payload, Mapping):
        return _closing_value(source_payload)
    return None


class RfqOperationalClassificationService:
    def classify(
        self,
        rfq: Mapping[str, Any],
        *,
        now: Optional[datetime] = None,
    ) -> RfqClassificationResult:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=BUSINESS_TIMEZONE)
        current = current.astimezone(timezone.utc)

        normalized_status, status_blob = _normalize_status(rfq)
        title_blob = f"{rfq.get('title') or ''} {rfq.get('description') or ''} {rfq.get('rfq_number') or ''}".lower()
        closing_at, date_error = _parse_closing(_closing_value(rfq))

        if "test" in title_blob or "demo" in title_blob or "script-" in title_blob:
            return RfqClassificationResult(RfqOperationalClassification.HISTORICAL, HistoricalReason.TEST_RFQ.value, normalized_status, closing_at, 0.98)
        if "award" in status_blob or "awarded" in status_blob:
            return RfqClassificationResult(RfqOperationalClassification.HISTORICAL, HistoricalReason.AWARDED.value, normalized_status, closing_at, 0.99)
        for token, reason in (
            ("cancel", HistoricalReason.CANCELLED.value),
            ("withdraw", HistoricalReason.WITHDRAWN.value),
            ("supersed", HistoricalReason.SUPERSEDED.value),
            ("archiv", HistoricalReason.ARCHIVED.value),
            ("historical", HistoricalReason.HISTORICAL_NOTICE.value),
            ("closed", HistoricalReason.CLOSED.value),
            ("expired", HistoricalReason.EXPIRED.value),
            ("submitted", HistoricalReason.ARCHIVED_SUBMISSION.value),
            ("proof", HistoricalReason.ARCHIVED_SUBMISSION.value),
        ):
            if token in status_blob:
                return RfqClassificationResult(RfqOperationalClassification.HISTORICAL, reason, normalized_status, closing_at, 0.96)

        if date_error:
            reason = date_error
            if normalized_status and normalized_status not in {"PUBLISHED", "ACTIVE", "OPEN", "LIVE", "DISCOVERED", "QUALIFIED", "REVIEW_REQUIRED", "PRICING"}:
                reason = ReviewReason.AMBIGUOUS_STATUS.value
            return RfqClassificationResult(RfqOperationalClassification.REVIEW_REQUIRED, reason, normalized_status, None, 0.9)

        assert closing_at is not None
        if closing_at <= current:
            return RfqClassificationResult(RfqOperationalClassification.HISTORICAL, HistoricalReason.EXPIRED.value, normalized_status, closing_at, 0.99)

        if normalized_status and normalized_status in {"REJECTED", "FAILED", "BLOCKED"}:
            return RfqClassificationResult(RfqOperationalClassification.REVIEW_REQUIRED, ReviewReason.CONFLICTING_LIFECYCLE_DATA.value, normalized_status, closing_at, 0.82)

        record_text = f"{rfq.get('type') or ''} {rfq.get('request_type') or ''} {rfq.get('title') or ''} {rfq.get('description') or ''}".lower()
        if not any(term in record_text for term in ("rfq", "request for quotation", "tender", "bid", "supply", "deliver", "delivery")):
            return RfqClassificationResult(RfqOperationalClassification.REVIEW_REQUIRED, ReviewReason.UNKNOWN_RECORD_TYPE.value, normalized_status, closing_at, 0.75)

        return RfqClassificationResult(RfqOperationalClassification.ACTIVE, "ACTIVE_FUTURE_CLOSING_DATE", normalized_status, closing_at, 0.97)
