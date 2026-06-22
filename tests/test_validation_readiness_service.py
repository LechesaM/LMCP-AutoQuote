from __future__ import annotations

from pathlib import Path

from app.services.validation_readiness_service import build_validation_readiness


def test_validation_readiness_reports_complete_metadata_for_ready_payload() -> None:
    result = build_validation_readiness(
        {
            "tender_id": "R-READY",
            "title": "Supply and delivery of office consumables",
            "buyer_name": "Metro Procurement Unit",
            "category": "office supplies",
            "submission_method": "email",
            "source_url": "https://example.org/tenders/R-READY",
            "detail_url": "https://example.org/tenders/R-READY/detail",
            "closing_date": "2030-01-01T12:00:00Z",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
            "document_confidence_score": 0.92,
        }
    )

    assert result["readiness_state"] == "READY"
    assert result["validation_subtype"] == "NONE"
    assert result["validation_subtypes"] == ["NONE"]
    assert result["metadata_completeness_state"] == "COMPLETE"
    assert result["metadata_missing_fields"] == []
    assert result["metadata_issue_codes"] == []


def test_validation_readiness_prioritizes_metadata_completeness_for_missing_metadata() -> None:
    result = build_validation_readiness(
        {
            "tender_id": "R-META",
            "title": "Supply and delivery of office consumables",
            "buyer_name": "Metro Procurement Unit",
            "category": "office supplies",
            "submission_method": "email",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
            "document_confidence_score": 0.4,
        }
    )

    assert result["validation_subtype"] == "METADATA_COMPLETENESS"
    assert "METADATA_COMPLETENESS" in result["validation_subtypes"]
    assert result["metadata_completeness_state"] == "INCOMPLETE"
    assert "closing_date" in result["metadata_missing_fields"]
    assert "source_url" in result["metadata_missing_fields"]
    assert "detail_url" in result["metadata_missing_fields"]
    assert "metadata_missing_closing_date" in result["metadata_issue_codes"]
    assert "metadata_missing_source_or_detail_url" in result["metadata_issue_codes"]
    assert result["metadata_recovered_document_confidence"] >= 0.4


def test_validation_readiness_separates_qualification_and_technical_subtypes() -> None:
    qualification = build_validation_readiness(
        {
            "tender_id": "R-QUAL",
            "title": "Catering services for event",
            "buyer_name": "City of Example",
            "category": "catering",
            "submission_method": "email",
            "source_url": "https://example.org/tenders/R-QUAL",
            "detail_url": "https://example.org/tenders/R-QUAL/detail",
            "closing_date": "2030-01-01T12:00:00Z",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
            "document_confidence_score": 0.9,
        }
    )
    technical = build_validation_readiness(
        {
            "tender_id": "R-TECH",
            "title": "Supply and delivery of building materials",
            "buyer_name": "City of Example",
            "category": "building materials",
            "submission_method": "email",
            "source_url": "https://example.org/tenders/R-TECH",
            "detail_url": "https://example.org/tenders/R-TECH/detail",
            "closing_date": "2030-01-01T12:00:00Z",
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
            "document_confidence_score": 0.9,
        }
    )

    assert qualification["validation_subtype"] == "QUALIFICATION_EXCLUSION"
    assert "QUALIFICATION_EXCLUSION" in qualification["validation_subtypes"]
    assert technical["validation_subtype"] == "TECHNICAL_VALIDATION"
    assert "TECHNICAL_VALIDATION" in technical["validation_subtypes"]


def test_validation_readiness_recovers_metadata_from_local_provenance(tmp_path: Path) -> None:
    provenance = tmp_path / "R-RECOVER_overview.txt"
    provenance.write_text(
        "\n".join(
            [
                "Closing date: 2030-01-01 12:00",
                "Submission method: email",
                "Source URL: https://example.org/tenders/R-RECOVER",
                "Detail URL: https://example.org/tenders/R-RECOVER/detail",
            ]
        )
    )

    result = build_validation_readiness(
        {
            "tender_id": "R-RECOVER",
            "title": "Supply and delivery of office consumables",
            "buyer_name": "Metro Procurement Unit",
            "category": "office supplies",
            "documents": [{"source_path": str(provenance)}],
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
        }
    )

    assert result["readiness_state"] == "READY"
    assert result["validation_subtype"] == "NONE"
    assert result["metadata_completeness_state"] == "COMPLETE"
    assert result["metadata_missing_fields"] == []
    assert result["metadata_recovery_paths"]
    assert result["metadata_recovered_submission_method"] == "email"
    assert result["metadata_recovered_closing_date"] == "2030-01-01 12:00"
    assert result["metadata_recovered_source_url"] == "https://example.org/tenders/R-RECOVER"
    assert result["metadata_recovered_detail_url"] == "https://example.org/tenders/R-RECOVER/detail"
    assert result["metadata_recovered_document_confidence"] >= 0.75


def test_validation_readiness_recovery_exposes_document_signals(tmp_path: Path) -> None:
    provenance = tmp_path / "R-RECOVER-DOCS_overview.txt"
    provenance.write_text(
        "\n".join(
            [
                "Closing date: 2030-01-01 12:00",
                "Submission method: email",
                "Source URL: https://example.org/tenders/R-RECOVER-DOCS",
                "Detail URL: https://example.org/tenders/R-RECOVER-DOCS/detail",
                "Pricing schedule attached",
                "SBD and returnables attached",
            ]
        )
    )

    result = build_validation_readiness(
        {
            "tender_id": "R-RECOVER-DOCS",
            "title": "Supply and delivery of office consumables",
            "buyer_name": "Metro Procurement Unit",
            "category": "office supplies",
            "documents": [{"source_path": str(provenance)}],
            "estimated_profit": 50000.0,
            "gross_margin_ratio": 0.3,
        }
    )

    assert result["readiness_state"] == "READY"
    assert result["metadata_completeness_state"] == "COMPLETE"
    assert result["metadata_recovered_source_url"] == "https://example.org/tenders/R-RECOVER-DOCS"
    assert result["metadata_recovered_detail_url"] == "https://example.org/tenders/R-RECOVER-DOCS/detail"
    assert "pricing_schedule" in result["metadata_recovery_signals"]
    assert "sbd_or_returnables" in result["metadata_recovery_signals"]
