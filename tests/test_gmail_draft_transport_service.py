from datetime import datetime, timezone

import pytest

from app.services.gmail_draft_transport_service import (
    EmailTransportOperationBlocked,
    FakeGmailDraftClient,
    GmailAttachmentRequest,
    GmailDraftRequest,
    GmailDraftTransportService,
    GmailDraftValidationError,
    build_gmail_mime_message,
    build_supplier_gmail_draft_request,
    encode_gmail_raw_message,
    inspect_gmail_draft_capability,
    resolve_transport_mode,
)
from app.services.gmail_oauth_provider import GmailOAuthConfig, GmailOAuthProvider
from app.services.supplier_outreach_service import (
    DEFAULT_MANDATORY_CC,
    DEFAULT_SUPPLIER_MAILBOX,
    EMAIL_TYPE_CLARIFICATION,
    EMAIL_TYPE_FOLLOWUP_1,
    EMAIL_TYPE_INITIAL,
    build_supplier_email_model,
)
from scripts.gmail_draft_transport_mock_validation_6000080579 import run_validation


def _pack():
    return {
        "reference_number": "6000080579",
        "buyer_name": "Johannesburg Water SOC Ltd",
        "title": "Supply and Delivery of Heavy Duty Hand Tools",
        "buyer_rows": [{"brand_required": True, "datasheet_required": True, "sample_may_be_required": True, "standards": ["SANS 1028"]}],
        "supplier_sourcing_groups": [
            {"supplier_group_id": f"SUP-{m}", "material_number": m, "description": d, "total_quantity": q, "unit": "EA", "standards": s, "brand_required": True, "datasheet_required": True, "sample_may_be_required": True}
            for m, d, q, s in [
                ("327", "Straight Pipe Wrench 350 mm Heavy Duty", 80, ["SANS 1028"]),
                ("315", "Shifting/Open-End Adjustable Spanner 250 mm Heavy Duty", 50, ["ISO 6787", "SANS 1211"]),
                ("302", "Club Hammer 1.8 kg Steel-Reinforced Polymer Handle", 224, ["SANS 387"]),
                ("328", "Straight Pipe Wrench 450 mm Heavy Duty", 280, ["SANS 1028"]),
                ("1304", "Cold Flat Chisel 200 mm x 20 mm", 40, []),
                ("316", "Shifting/Open-End Adjustable Spanner 300 mm Heavy Duty", 40, ["ISO 6787", "SANS 1211"]),
            ]
        ],
    }


def _email_model():
    return build_supplier_email_model(
        supplier={"supplier_name": "Controlled", "supplier_email": DEFAULT_SUPPLIER_MAILBOX},
        requirement_pack=_pack(),
        request_id="LMCP-SRFQ-6000080579-341E812698",
        created_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        response_deadline="2026-07-19T08:00:00+00:00",
    )


def _attachment(name="schedule.json", content=b"{}"):
    return GmailAttachmentRequest(filename=name, mime_type="application/json", content=content, logical_document_type="test").normalised()


def _request(email_type=EMAIL_TYPE_INITIAL, recipient=DEFAULT_SUPPLIER_MAILBOX):
    return build_supplier_gmail_draft_request(_email_model(), recipient=recipient, email_type=email_type, attachments=[_attachment()])


def test_transport_modes_draft_only_default_and_disabled_blocks_creation():
    assert resolve_transport_mode({}) == "DRAFT_ONLY"
    assert (
        resolve_transport_mode(
            {"LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY"}
        )
        == "DRAFT_ONLY"
    )
    assert (
        resolve_transport_mode(
            {"LMCP_EMAIL_TRANSPORT_MODE": "nonsense"}
        )
        == "DISABLED"
    )
    assert (
        resolve_transport_mode(
            {"LMCP_EMAIL_TRANSPORT_MODE": "DISABLED"}
        )
        == "DISABLED"
    )

    draft_client = FakeGmailDraftClient()
    draft_service = GmailDraftTransportService(
        gmail_client=draft_client,
        env={},
    )

    result = draft_service.create_draft(_request())

    assert result is not None
    assert result.redacted_draft_reference
    assert result.transport_mode == "DRAFT_ONLY"
    assert result.status == "DRAFT"
    assert result.duplicate_suppressed is False

    disabled_service = GmailDraftTransportService(
        gmail_client=FakeGmailDraftClient(),
        env={"LMCP_EMAIL_TRANSPORT_MODE": "DISABLED"},
    )

    with pytest.raises(EmailTransportOperationBlocked):
        disabled_service.create_draft(_request())


def test_draft_only_allows_create_list_get_and_blocks_send_paths():
    service = GmailDraftTransportService(gmail_client=FakeGmailDraftClient(), env={"LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY"})
    ref = service.create_draft(_request())
    assert ref.status == "DRAFT"
    summaries = service.list_drafts()
    assert len(summaries) == 1
    assert summaries[0].cc == [DEFAULT_MANDATORY_CC]
    message = service.get_draft(ref)
    assert message.summary.subject.startswith("LMCP AUTOQUOTE CONTROLLED DRAFT TEST")
    for fn, arg in [
        (service.send_email, _request()),
        (service.send_draft, ref),
        (service.smtp_fallback_send, _request()),
        (service.scheduler_dispatch, _request()),
    ]:
        with pytest.raises(EmailTransportOperationBlocked):
            fn(arg)


def test_addressing_policy_mandatory_cc_case_dedupe_bcc_and_bad_recipient():
    request = _request()
    request.cc = ["LECHESAM@ME.COM", DEFAULT_MANDATORY_CC]
    request.bcc = [DEFAULT_MANDATORY_CC]
    service = GmailDraftTransportService(gmail_client=FakeGmailDraftClient(), env={"LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY"})
    ref = service.create_draft(request)
    message = service.get_draft(ref)
    assert message.summary.cc == [DEFAULT_MANDATORY_CC]
    assert "bcc" not in {k.lower() for k in message.decoded_headers}
    with pytest.raises(GmailDraftValidationError):
        service.create_draft(_request(recipient="real-supplier@example.com"))
    bad = _request()
    bad.to = ["not-an-address"]
    with pytest.raises(GmailDraftValidationError):
        service.create_draft(bad)


def test_mime_generation_utf8_attachments_checksums_and_unsafe_rejection():
    request = _request()
    request.body_text += "\nUTF-8 check: × quotation schedule"
    request.attachments = [_attachment("a.json", b"a"), _attachment("b.json", b"b")]
    msg = build_gmail_mime_message(request)
    raw = encode_gmail_raw_message(msg)
    assert raw
    assert "Bcc" not in msg
    assert all(a.checksum for a in request.attachments)
    with pytest.raises(GmailDraftValidationError):
        GmailAttachmentRequest(filename="payload.exe", mime_type="application/x-msdownload", content=b"MZ").normalised()


def test_supplier_content_preserves_request_rfq_groups_quantities_and_standards():
    request = _request()
    assert request.supplier_request_id == "LMCP-SRFQ-6000080579-341E812698"
    assert request.rfq_id == "TEMP-RFQ-6000080579"
    for text in ["327", "80", "302", "224", "328", "280", "SANS 1028", "ISO 6787", "SANS 1211", "SANS 387"]:
        assert text in request.body_text
    assert "Offered brand required: True" in request.body_text
    assert "Manufacturer datasheet required: True" in request.body_text
    assert "Sample may be requested: True" in request.body_text
    assert "gross profit" not in request.body_text.lower()


def test_initial_followup_and_clarification_models_have_separate_idempotency_keys():
    initial = _request(EMAIL_TYPE_INITIAL)
    followup = _request(EMAIL_TYPE_FOLLOWUP_1)
    clarification = build_supplier_gmail_draft_request(
        _email_model(),
        recipient=DEFAULT_SUPPLIER_MAILBOX,
        email_type=EMAIL_TYPE_CLARIFICATION,
        missing_fields=["brand", "datasheet"],
    )
    assert len({initial.idempotency_key, followup.idempotency_key, clarification.idempotency_key}) == 3
    assert "Calculated follow-up due time" in followup.body_text
    assert "Missing information requested" in clarification.body_text


def test_idempotent_duplicate_suppression():
    service = GmailDraftTransportService(gmail_client=FakeGmailDraftClient(), env={"LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY"})
    first = service.create_draft(_request())
    second = service.create_draft(_request())
    assert second.redacted_draft_reference == first.redacted_draft_reference
    assert second.duplicate_suppressed is True
    assert len(service.list_drafts()) == 1


def test_dependency_and_oauth_configuration_errors_are_controlled_and_redacted():
    provider = GmailOAuthProvider(GmailOAuthConfig(client_secret_file="", token_file=""))
    inspection = provider.inspect_configuration()
    assert inspection["status"] in {"configuration_missing", "dependency_unavailable"}
    assert "redacted" not in inspection["redacted_client_secret_file"]
    cap = inspect_gmail_draft_capability({})
    assert cap["transport_mode"] == "DRAFT_ONLY"
    assert cap["credentials_exposed"] is False


def test_application_import_not_required_for_gmail_credentials():
    import app.main  # noqa: F401


def test_mock_validation_script_contract(tmp_path):
    dry_run = __import__("pathlib").Path("/tmp/lmcp-supplier-outreach-6000080579/outputs/supplier_outreach_dry_run.json")
    if not dry_run.exists():
        return
    report = run_validation(outreach_path=dry_run, output_root=tmp_path / "gmail-draft-mock")
    assert report["result"] == "PASS"
    assert report["draft_count"] == 3
    assert report["emails_sent"] == 0
    assert report["validation_checks"]["scheduler_blocked"] is True
