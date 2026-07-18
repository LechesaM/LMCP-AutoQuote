from datetime import datetime, timezone

from app.services.rfq_operational_classification_service import (
    RfqOperationalClassification,
    RfqOperationalClassificationService,
)


NOW = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)


def classify(payload):
    return RfqOperationalClassificationService().classify(payload, now=NOW)


def test_future_closing_date_is_active():
    result = classify({"title": "Supply and delivery of tools", "closing_date": "2026-07-22T12:00:00+02:00", "status": "Published"})
    assert result.classification == RfqOperationalClassification.ACTIVE
    assert result.reason == "ACTIVE_FUTURE_CLOSING_DATE"


def test_closing_later_today_is_active():
    result = classify({"title": "RFQ supply", "closing_date": "2026-07-18T16:00:00+02:00", "status": "Open"})
    assert result.classification == RfqOperationalClassification.ACTIVE


def test_passed_closing_datetime_is_historical_expired():
    result = classify({"title": "RFQ supply", "closing_date": "2026-07-17T16:00:00+02:00", "status": "Published"})
    assert result.classification == RfqOperationalClassification.HISTORICAL
    assert result.reason == "EXPIRED"


def test_historical_statuses_override_future_date():
    for status, reason in [
        ("Cancelled", "CANCELLED"),
        ("Awarded", "AWARDED"),
        ("Withdrawn", "WITHDRAWN"),
        ("Superseded", "SUPERSEDED"),
        ("Closed", "CLOSED"),
        ("Archived", "ARCHIVED"),
    ]:
        result = classify({"title": "Supply RFQ", "closing_date": "2026-08-01T12:00:00+02:00", "status": status})
        assert result.classification == RfqOperationalClassification.HISTORICAL
        assert result.reason == reason


def test_test_rfq_and_award_notice_are_historical():
    assert classify({"title": "TEST RFQ", "closing_date": "2026-08-01"}).reason == "TEST_RFQ"
    assert classify({"title": "Award notice for valves", "closing_date": "2026-08-01", "record_type": "Award notice"}).reason == "AWARDED"


def test_missing_and_malformed_dates_require_review():
    missing = classify({"title": "Supply RFQ", "status": "Published"})
    malformed = classify({"title": "Supply RFQ", "closing_date": "not a date", "status": "Published"})
    assert missing.classification == RfqOperationalClassification.REVIEW_REQUIRED
    assert missing.reason == "MISSING_CLOSING_DATE"
    assert malformed.classification == RfqOperationalClassification.REVIEW_REQUIRED
    assert malformed.reason == "INVALID_CLOSING_DATE"


def test_ambiguous_record_type_requires_review():
    result = classify({"title": "General administrative notice", "closing_date": "2026-08-01", "status": "Published"})
    assert result.classification == RfqOperationalClassification.REVIEW_REQUIRED
    assert result.reason == "UNKNOWN_RECORD_TYPE"


def test_naive_south_african_date_is_timezone_normalized():
    result = classify({"title": "Supply and delivery RFQ", "closing_date": "2026-07-19 12:00", "status": "Published"})
    assert result.normalized_closing_at is not None
    assert result.normalized_closing_at.tzinfo is not None
    assert result.classification == RfqOperationalClassification.ACTIVE
