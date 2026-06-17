from __future__ import annotations

from pathlib import Path

from app.services import manual_approval_service, submission_review_service
from app.services.email_submission_service import EmailSubmissionService
from app.services.tender_submission_pipeline import submit_tender_to_portal


def _patch_manual_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(manual_approval_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(manual_approval_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(manual_approval_service, "APPROVAL_LOG_FILE", manual_dir / "approvals.jsonl")

    monkeypatch.setattr(submission_review_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(submission_review_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(submission_review_service, "SUBMISSION_REVIEW_LOG_FILE", manual_dir / "submission_reviews.jsonl")
    return runtime_dir


def _seed_review_ready_gate(*, tender_id: str, tender_root: Path, pricing_file: Path) -> None:
    approval_record = manual_approval_service.build_manual_approval_record(
        {
            "tender_id": tender_id,
            "tender_root": str(tender_root),
            "pricing_file": str(pricing_file),
            "quote_pack_quality_status": "approval_ready",
            "warnings": [],
            "approval_blocked": False,
            "pricing_items_unmatched": 0,
            "final_submission_attempted": False,
        },
        tender_id=tender_id,
        tender_root=str(tender_root),
        pricing_file=str(pricing_file),
        operator_name="Operator",
        confirm_approval=True,
    )
    manual_approval_service.append_manual_approval(approval_record)

    review_record = submission_review_service.build_submission_review_record(
        tender_id=tender_id,
        tender_root=str(tender_root),
        pricing_file=str(pricing_file),
        operator_name="Reviewer",
    )
    submission_review_service.append_submission_review(review_record)


def test_email_submission_blocks_without_review_ready(monkeypatch, tmp_path: Path) -> None:
    _patch_manual_runtime(monkeypatch, tmp_path)
    tender_root = tmp_path / "tender"
    tender_root.mkdir()
    pdf_path = tender_root / "RFQ-1__quote_pack.pdf"
    pdf_path.write_text("quote pack", encoding="utf-8")
    pricing_file = tender_root / "pricing.json"
    pricing_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(EmailSubmissionService, "send_email", classmethod(lambda cls, **_: {"success": True, "submitted": True, "status": "sent", "message": "sent"}))

    result = EmailSubmissionService.submit_quote_email(
        {
            "tender_id": "RFQ-1",
            "tender_root": str(tender_root),
            "quote_pack": {"submission_method": "email"},
            "submission_pack": {"submission_method": "email"},
            "recipient_email": "buyer@example.com",
            "to_email": "buyer@example.com",
            "final_pdf_path": str(pdf_path),
            "attachment_paths": [str(pdf_path)],
            "pricing_file": str(pricing_file),
            "subject": "Quotation Submission",
        }
    )

    assert result["status"] == "manual_action_required"
    assert result["human_approval_required"] is True
    assert result["human_approval_granted"] is False
    assert "manual approval record missing" in result["review_blockers"]


def test_email_submission_allows_review_ready(monkeypatch, tmp_path: Path) -> None:
    _patch_manual_runtime(monkeypatch, tmp_path)
    tender_root = tmp_path / "tender"
    tender_root.mkdir()
    pdf_path = tender_root / "RFQ-2__quote_pack.pdf"
    pdf_path.write_text("quote pack", encoding="utf-8")
    (tender_root / "RFQ-2_submission_pack_manifest.txt").write_text("submission pack", encoding="utf-8")
    rfq_path = tender_root / "rfq.pdf"
    rfq_path.write_text("rfq", encoding="utf-8")
    pricing_file = tender_root / "pricing.json"
    pricing_file.write_text("{}", encoding="utf-8")

    _seed_review_ready_gate(tender_id="RFQ-2", tender_root=tender_root, pricing_file=pricing_file)

    monkeypatch.setattr(
        EmailSubmissionService,
        "send_email",
        classmethod(lambda cls, **_: {"success": True, "submitted": True, "status": "sent", "message": "sent"}),
    )

    result = EmailSubmissionService.submit_quote_email(
        {
            "tender_id": "RFQ-2",
            "tender_root": str(tender_root),
            "quote_pack": {"submission_method": "email"},
            "submission_pack": {"submission_method": "email"},
            "recipient_email": "buyer@example.com",
            "to_email": "buyer@example.com",
            "final_pdf_path": str(pdf_path),
            "attachment_paths": [str(pdf_path)],
            "pricing_file": str(pricing_file),
            "subject": "Quotation Submission",
        }
    )

    assert result["success"] is True
    assert result["status"] == "sent"
    assert result["human_approval_required"] is True
    assert result["human_approval_granted"] is True
    assert result["submission_review_status"] == "review_ready"
    assert result["submission_review_ready"] is True


def test_portal_submission_requires_review_ready_before_automation(monkeypatch, tmp_path: Path) -> None:
    _patch_manual_runtime(monkeypatch, tmp_path)
    tender_root = tmp_path / "tender"
    tender_root.mkdir()
    pdf_path = tender_root / "RFQ-3__quote_pack.pdf"
    pdf_path.write_text("quote pack", encoding="utf-8")
    pricing_file = tender_root / "pricing.json"
    pricing_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("app.services.tender_submission_pipeline.PORTAL_AUTOMATION_ENABLED", True)
    monkeypatch.setattr(
        "app.services.tender_submission_pipeline._run_generic_playwright_submission",
        lambda payload: (_ for _ in ()).throw(AssertionError("portal automation should not run before human approval")),
    )

    blocked = submit_tender_to_portal(
        {
            "tender_id": "RFQ-3",
            "tender_root": str(tender_root),
            "portal_url": "https://portal.example.com",
            "final_pdf_path": str(pdf_path),
            "pdf_path": str(pdf_path),
            "attachment_paths": [str(pdf_path)],
            "pricing_file": str(pricing_file),
            "buyer_rfq_number": "RFQ-3",
            "submission_method": "portal",
        }
    )

    assert blocked["status"] == "manual_action_required"
    assert blocked["human_approval_required"] is True
    assert blocked["human_approval_granted"] is False


def test_portal_submission_allows_review_ready_before_automation(monkeypatch, tmp_path: Path) -> None:
    _patch_manual_runtime(monkeypatch, tmp_path)
    tender_root = tmp_path / "tender"
    tender_root.mkdir()
    pdf_path = tender_root / "RFQ-4__quote_pack.pdf"
    pdf_path.write_text("quote pack", encoding="utf-8")
    (tender_root / "RFQ-4_submission_pack_manifest.txt").write_text("submission pack", encoding="utf-8")
    (tender_root / "rfq.pdf").write_text("rfq", encoding="utf-8")
    pricing_file = tender_root / "pricing.json"
    pricing_file.write_text("{}", encoding="utf-8")

    _seed_review_ready_gate(tender_id="RFQ-4", tender_root=tender_root, pricing_file=pricing_file)

    monkeypatch.setattr("app.services.tender_submission_pipeline.PORTAL_AUTOMATION_ENABLED", True)
    monkeypatch.setattr(
        "app.services.tender_submission_pipeline._run_generic_playwright_submission",
        lambda payload: {"success": True, "status": "submitted", "message": "portal submitted", "uploaded_files": payload.get("attachment_paths", [])},
    )

    result = submit_tender_to_portal(
        {
            "tender_id": "RFQ-4",
            "tender_root": str(tender_root),
            "portal_url": "https://portal.example.com",
            "final_pdf_path": str(pdf_path),
            "pdf_path": str(pdf_path),
            "attachment_paths": [str(pdf_path)],
            "pricing_file": str(pricing_file),
            "buyer_rfq_number": "RFQ-4",
            "submission_method": "portal",
        }
    )

    assert result["success"] is True
    assert result["status"] == "submitted"
