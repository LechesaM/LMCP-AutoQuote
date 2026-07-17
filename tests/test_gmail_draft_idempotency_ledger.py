import threading
from pathlib import Path

import pytest

from app.services.gmail_draft_idempotency_ledger import (
    EXPECTED_REQUEST_ID,
    EXPECTED_RFQ_REFERENCE,
    canonical_idempotency_key,
    canonical_key_for_request,
    load_ledger,
    load_ledger_with_status,
    locked_ledger,
    resolve_or_create_draft,
    save_ledger_atomic,
    stable_hash,
    validate_message,
)
from app.services.gmail_draft_transport_service import (
    EmailTransportOperationBlocked,
    FakeGmailDraftClient,
    GmailDraftTransportService,
    GmailDraftValidationError,
)
from app.services.supplier_outreach_service import DEFAULT_MANDATORY_CC, DEFAULT_SUPPLIER_MAILBOX
from scripts.gmail_real_draft_validation_6000080579 import _attachments, _request


def _service():
    return GmailDraftTransportService(
        gmail_client=FakeGmailDraftClient(),
        env={"LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY", "LMCP_GMAIL_USER_ID": "me"},
        controlled_test_mode=True,
    )


def _service_with_client(client):
    return GmailDraftTransportService(
        gmail_client=client,
        env={"LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY", "LMCP_GMAIL_USER_ID": "me"},
        controlled_test_mode=True,
    )


def _requests(tmp_path):
    attachments = _attachments(tmp_path)
    return [
        ("initial", _request("initial", attachments)),
        ("follow-up", _request("followup", attachments)),
        ("clarification", _request("clarification", attachments)),
    ]


def _resolve_all(service, ledger, tmp_path):
    out = []
    for draft_type, request in _requests(tmp_path):
        out.append(resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject))
    return out


def test_fresh_state_first_run_creates_then_second_run_reuses(tmp_path):
    service = _service()
    ledger_path = tmp_path / "state" / "draft_idempotency_ledger.json"
    ledger = load_ledger(ledger_path)
    first = _resolve_all(service, ledger, tmp_path)
    save_ledger_atomic(ledger_path, ledger)
    assert sum(item.new_draft_created for item in first) == 3
    assert len(service.list_drafts()) == 3
    assert oct(ledger_path.stat().st_mode & 0o777) == "0o600"

    ledger2 = load_ledger(ledger_path)
    second = _resolve_all(service, ledger2, tmp_path)
    assert sum(item.new_draft_created for item in second) == 0
    assert sum(item.canonical_reused for item in second) == 3
    assert sum(item.duplicate_suppressed for item in second) == 3
    assert len(service.list_drafts()) == 3


def test_same_request_in_two_transport_instances_reuses_shared_fake_gmail_draft(tmp_path):
    client = FakeGmailDraftClient()
    service1 = _service_with_client(client)
    service2 = _service_with_client(client)
    draft_type, request = _requests(tmp_path)[0]
    ledger_path = tmp_path / "state" / "draft_idempotency_ledger.json"
    ledger = load_ledger(ledger_path)
    first = resolve_or_create_draft(service=service1, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    save_ledger_atomic(ledger_path, ledger)
    ledger2 = load_ledger(ledger_path)
    second = resolve_or_create_draft(service=service2, ledger=ledger2, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert first.new_draft_created is True
    assert second.new_draft_created is False
    assert second.canonical_reused is True
    assert len(service2.list_drafts()) == 1


def test_canonical_key_normalisation_and_distinct_business_inputs(tmp_path):
    _, request = _requests(tmp_path)[0]
    reordered = canonical_idempotency_key(
        mailbox=DEFAULT_SUPPLIER_MAILBOX.upper(),
        rfq_id=request.rfq_id + "  ",
        supplier_identity=DEFAULT_SUPPLIER_MAILBOX.upper(),
        operation=" INITIAL ",
        recipients=[DEFAULT_MANDATORY_CC, DEFAULT_SUPPLIER_MAILBOX],
        cc=[DEFAULT_MANDATORY_CC.upper()],
        subject=request.subject + "  ",
        body=request.body_text.replace("\n", "\r\n") + "   ",
    )
    reordered_2 = canonical_idempotency_key(
        mailbox=DEFAULT_SUPPLIER_MAILBOX,
        rfq_id=request.rfq_id,
        supplier_identity=DEFAULT_SUPPLIER_MAILBOX,
        operation="initial",
        recipients=[DEFAULT_SUPPLIER_MAILBOX, DEFAULT_MANDATORY_CC],
        cc=[DEFAULT_MANDATORY_CC],
        subject=request.subject,
        body=request.body_text,
    )
    assert reordered == reordered_2
    assert canonical_key_for_request(DEFAULT_SUPPLIER_MAILBOX, request, "initial") != canonical_idempotency_key(
        mailbox=DEFAULT_SUPPLIER_MAILBOX,
        rfq_id="TEMP-RFQ-DIFFERENT",
        supplier_identity=DEFAULT_SUPPLIER_MAILBOX,
        operation="initial",
        recipients=request.to,
        cc=request.cc,
        subject=request.subject,
        body=request.body_text,
    )
    assert canonical_key_for_request(DEFAULT_SUPPLIER_MAILBOX, request, "initial") != canonical_idempotency_key(
        mailbox=DEFAULT_SUPPLIER_MAILBOX,
        rfq_id=request.rfq_id,
        supplier_identity="other-controlled@example.test",
        operation="initial",
        recipients=["other-controlled@example.test"],
        cc=request.cc,
        subject=request.subject,
        body=request.body_text,
    )
    assert canonical_key_for_request(DEFAULT_SUPPLIER_MAILBOX, request, "initial") != canonical_idempotency_key(
        mailbox=DEFAULT_SUPPLIER_MAILBOX,
        rfq_id=request.rfq_id,
        supplier_identity=DEFAULT_SUPPLIER_MAILBOX,
        operation="initial",
        recipients=request.to,
        cc=request.cc,
        subject=request.subject,
        body=request.body_text + "\nSubstantive added requirement.",
    )

def test_stale_ledger_adopts_existing_matching_draft(tmp_path):
    service = _service()
    draft_type, request = _requests(tmp_path)[0]
    created = service.create_draft(request)
    message = service.get_draft(created)
    ledger = load_ledger(tmp_path / "ledger.json")
    key = request.idempotency_key
    ledger["entries"][key] = {
        "raw_gmail_draft_reference": "missing-draft",
        "redacted_gmail_draft_reference": "redacted-missing",
    }
    result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert result.new_draft_created is False
    assert result.canonical_reused is True
    assert result.stale_ledger_reference is True
    assert result.message.summary.subject == message.summary.subject
    assert len(service.list_drafts()) == 1


def test_corrupt_ledger_discovers_existing_draft_without_creating(tmp_path):
    service = _service()
    draft_type, request = _requests(tmp_path)[0]
    service.create_draft(request)
    ledger_path = tmp_path / "state" / "draft_idempotency_ledger.json"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text("{not-json", encoding="utf-8")
    ledger, corrupt, _ = load_ledger_with_status(ledger_path)
    result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject, allow_create=not corrupt)
    assert corrupt is True
    assert result.new_draft_created is False
    assert result.canonical_reused is True
    assert len(service.list_drafts()) == 1


def test_corrupt_ledger_without_discovery_fails_before_creation(tmp_path):
    service = _service()
    draft_type, request = _requests(tmp_path)[0]
    ledger_path = tmp_path / "state" / "draft_idempotency_ledger.json"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text("{not-json", encoding="utf-8")
    ledger, corrupt, _ = load_ledger_with_status(ledger_path)
    with pytest.raises(GmailDraftValidationError):
        resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject, allow_create=not corrupt)
    assert len(service.list_drafts()) == 0


def test_ambiguous_discovery_selects_one_canonical_without_creating_third(tmp_path):
    service = _service()
    draft_type, request = _requests(tmp_path)[0]
    service.create_draft(request)
    # Simulate a real cross-run duplicate by bypassing fake-client idempotency.
    request2 = _request("initial", _attachments(tmp_path))
    request2.idempotency_key = request.idempotency_key + ":historical-duplicate"
    service.create_draft(request2)
    ledger = load_ledger(tmp_path / "ledger.json")
    result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert result.new_draft_created is False
    assert result.duplicates_detected == 1
    assert len(service.list_drafts()) == 2


def test_content_mismatch_rejects_ledger_and_uses_valid_discovery(tmp_path):
    service = _service()
    draft_type, request = _requests(tmp_path)[0]
    bad_request = _request("initial", _attachments(tmp_path))
    bad_request.body_text = bad_request.body_text.replace("DO NOT SEND.", "DO NOT USE.")
    bad = service.create_draft(bad_request)
    good_request = _request("initial", _attachments(tmp_path))
    good_request.idempotency_key = good_request.idempotency_key + ":valid-discovery"
    service.create_draft(good_request)
    ledger = load_ledger(tmp_path / "ledger.json")
    key = request.idempotency_key
    ledger["entries"][key] = {
        "raw_gmail_draft_reference": service.raw_reference_for_redacted(bad.redacted_draft_reference),
        "redacted_gmail_draft_reference": bad.redacted_draft_reference,
    }
    result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert result.new_draft_created is False
    assert result.stale_ledger_reference is True
    assert "DO NOT SEND" in result.message.body_text


@pytest.mark.parametrize(
    "mutator,expected_error",
    [
        (lambda req: setattr(req, "to", [DEFAULT_MANDATORY_CC]), "recipient_mismatch"),
        (lambda req: setattr(req, "cc", []), "mandatory_cc_mismatch"),
        (lambda req: setattr(req, "cc", [DEFAULT_MANDATORY_CC, "thirdparty@test.invalid"]), "mandatory_cc_mismatch"),
        (lambda req: setattr(req, "bcc", [DEFAULT_MANDATORY_CC]), "bcc_present"),
    ],
)
def test_addressing_mismatch_drafts_are_not_reused(tmp_path, mutator, expected_error):
    service = _service()
    draft_type, request = _requests(tmp_path)[0]
    mutated = _request("initial", _attachments(tmp_path))
    ref = service.create_draft(mutated)
    raw = service.raw_reference_for_redacted(ref.redacted_draft_reference)
    if expected_error == "recipient_mismatch":
        service.gmail_client._drafts[raw]["metadata"]["recipient"] = [DEFAULT_MANDATORY_CC]
    elif expected_error == "mandatory_cc_mismatch" and not mutated.cc:
        service.gmail_client._drafts[raw]["metadata"]["cc"] = []
    elif expected_error == "mandatory_cc_mismatch":
        service.gmail_client._drafts[raw]["metadata"]["cc"] = [DEFAULT_MANDATORY_CC, "thirdparty@test.invalid"]
    elif expected_error == "bcc_present":
        service.gmail_client._drafts[raw]["metadata"]["bcc"] = [DEFAULT_MANDATORY_CC]
    message = service.get_draft(ref)
    errors = validate_message(
        message,
        {
            "draft_type": draft_type,
            "subject": request.subject,
            "attachment_count": len(request.attachments),
            "stored_content_checksum": stable_hash(request.subject + "\n" + request.body_text.strip()),
        },
    )
    assert expected_error in errors


def test_send_interfaces_remain_blocked(tmp_path):
    service = _service()
    _, request = _requests(tmp_path)[0]
    ref = service.create_draft(request)
    for fn, arg in [
        (service.send_email, request),
        (service.send_draft, ref),
        (service.smtp_fallback_send, request),
        (service.scheduler_dispatch, request),
    ]:
        with pytest.raises(EmailTransportOperationBlocked):
            fn(arg)


def _historical_clarification(service, tmp_path, *, body_suffix="", subject_label="Clarification", mutate=None):
    _, request = _requests(tmp_path)[2]
    request.subject = f"LMCP CONTROLLED DRAFT TEST — DO NOT SEND | {subject_label} | 6000080579 | LMCP-SRFQ-6000080579-341E812698"
    request.body_text = request.body_text.replace("\n", "\r\n") + body_suffix
    request.idempotency_key = request.idempotency_key + f":historical:{len(service.gmail_client._drafts)}"
    ref = service.create_draft(request)
    raw = service.raw_reference_for_redacted(ref.redacted_draft_reference)
    metadata = service.gmail_client._drafts[raw]["metadata"]
    metadata.pop("draft_idempotency_key", None)
    if mutate:
        mutate(metadata)
    return ref


def test_historical_clarification_without_header_is_discovered(tmp_path):
    service = _service()
    _historical_clarification(service, tmp_path)
    draft_type, request = _requests(tmp_path)[2]
    ledger = load_ledger(tmp_path / "ledger.json")
    result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert result.new_draft_created is False
    assert result.canonical_reused is True
    assert len(service.list_drafts()) == 1


def test_clarification_line_endings_whitespace_mime_headers_and_attachment_order_do_not_block_discovery(tmp_path):
    service = _service()

    def mutate(metadata):
        metadata["body_text"] = metadata["body_text"].replace("\r\n", "\n") + "   \n"
        metadata["attachments"] = list(reversed(metadata["attachments"]))
        metadata["dynamic_gmail_header"] = "ignored"

    _historical_clarification(service, tmp_path, body_suffix="   \n", mutate=mutate)
    draft_type, request = _requests(tmp_path)[2]
    ledger = load_ledger(tmp_path / "ledger.json")
    result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert result.new_draft_created is False
    assert len(service.list_drafts()) == 1


def test_clarification_subject_alias_is_safe_but_material_body_difference_rejected(tmp_path):
    service = _service()
    _historical_clarification(service, tmp_path, subject_label="Clarification Request")
    draft_type, request = _requests(tmp_path)[2]
    ledger = load_ledger(tmp_path / "ledger.json")
    result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert result.new_draft_created is False

    service2 = _service()

    def mutate(metadata):
        metadata["body_text"] = metadata["body_text"].replace("- formal supplier quotation", "")

    _historical_clarification(service2, tmp_path, subject_label="Clarification Request", mutate=mutate)
    ledger2 = load_ledger(tmp_path / "ledger2.json")
    result2 = resolve_or_create_draft(service=service2, ledger=ledger2, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert result2.new_draft_created is True
    assert len(service2.list_drafts()) == 2


@pytest.mark.parametrize(
    "mutate,expected_error",
    [
        (lambda metadata: metadata.update({"body_text": metadata["body_text"].replace("6000080579", "")}), "rfq_reference_missing"),
        (lambda metadata: metadata.update({"body_text": metadata["body_text"].replace("LMCP-SRFQ-6000080579-341E812698", ""), "supplier_request_id": ""}), "request_id_missing"),
        (lambda metadata: metadata.update({"cc": []}), "mandatory_cc_mismatch"),
        (lambda metadata: metadata.update({"bcc": ["audit@example.test"]}), "bcc_present"),
        (lambda metadata: metadata.update({"body_text": metadata["body_text"] + "\nInternal profit: confidential"}), "internal_pricing_disclosure:profit"),
    ],
)
def test_clarification_rejects_unsafe_or_material_mismatches(tmp_path, mutate, expected_error):
    service = _service()
    ref = _historical_clarification(service, tmp_path, mutate=mutate)
    message = service.get_draft(ref)
    _, request = _requests(tmp_path)[2]
    errors = validate_message(
        message,
        {
            "draft_type": "clarification",
            "subject": request.subject,
            "subject_aliases": [request.subject],
            "attachment_count": len(request.attachments),
            "stored_content_checksum": stable_hash(request.subject + "\n" + request.body_text.strip()),
        },
    )
    assert expected_error in errors


def test_multiple_clarification_matches_select_oldest_and_create_zero(tmp_path):
    service = _service()
    _historical_clarification(service, tmp_path)
    request2_ref = _historical_clarification(service, tmp_path)
    draft_type, request = _requests(tmp_path)[2]
    ledger = load_ledger(tmp_path / "ledger.json")
    result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert result.new_draft_created is False
    assert result.duplicates_detected == 1
    assert result.reference.redacted_draft_reference != request2_ref.redacted_draft_reference
    assert len(service.list_drafts()) == 2


def test_stale_and_corrupt_ledger_with_valid_clarification_create_zero(tmp_path):
    service = _service()
    _historical_clarification(service, tmp_path)
    draft_type, request = _requests(tmp_path)[2]
    ledger = load_ledger(tmp_path / "ledger.json")
    ledger["entries"][request.idempotency_key] = {"raw_gmail_draft_reference": "missing"}
    stale = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
    assert stale.new_draft_created is False

    ledger_path = tmp_path / "corrupt.json"
    ledger_path.write_text("{not-json", encoding="utf-8")
    corrupt_ledger, corrupt, _ = load_ledger_with_status(ledger_path)
    recovered = resolve_or_create_draft(service=service, ledger=corrupt_ledger, draft_type=draft_type, request=request, expected_subject=request.subject, allow_create=not corrupt)
    assert corrupt is True
    assert recovered.new_draft_created is False
    assert len(service.list_drafts()) == 1


def test_locked_concurrent_attempts_create_at_most_one_draft(tmp_path):
    client = FakeGmailDraftClient()
    ledger_path = tmp_path / "state" / "draft_idempotency_ledger.json"
    draft_type, request = _requests(tmp_path)[0]
    results = []

    def worker():
        service = _service_with_client(client)
        with locked_ledger(ledger_path):
            ledger = load_ledger(ledger_path)
            result = resolve_or_create_draft(service=service, ledger=ledger, draft_type=draft_type, request=request, expected_subject=request.subject)
            save_ledger_atomic(ledger_path, ledger)
            results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    service = _service_with_client(client)
    assert len(service.list_drafts()) == 1
    assert sum(result.new_draft_created for result in results) == 1
