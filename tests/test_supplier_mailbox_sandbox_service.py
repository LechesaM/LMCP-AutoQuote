from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.supplier_mailbox_sandbox_service import (
    MATCH_REQUEST_ID_EXACT,
    PERMANENT_BOUNCE,
    SUPPLIER_DECLINED,
    SUPPLIER_RESPONSE_INCOMPLETE,
    VALID_SUPPLIER_QUOTATION,
    build_clarification_email_model,
    build_inbound_mime,
    build_mailbox_validation_no_response_state,
    build_outbound_mime,
    capture_attachment_manifest,
    classify_supplier_response,
    evaluate_followup_eligibility,
    match_supplier_response,
    parse_mime_message,
    safe_tmp_output_dir,
)
from app.services.supplier_outreach_service import (
    DEFAULT_MANDATORY_CC,
    DEFAULT_SUPPLIER_MAILBOX,
    build_supplier_email_model,
    enforce_mandatory_cc,
    select_supplier_targets,
)
from scripts.supplier_mailbox_sandbox_validation_6000080579 import run_validation


REQUEST_ID = "LMCP-SRFQ-6000080579-341E812698"


def _pack():
    return {
        "reference_number": "6000080579",
        "buyer_name": "Johannesburg Water SOC Ltd",
        "title": "Supply and Delivery of Heavy Duty Hand Tools",
        "buyer_rows": [
            {"standards": ["SANS 1028"], "brand_required": True, "datasheet_required": True, "sample_may_be_required": True}
        ],
        "technical_requirements": [],
        "supplier_sourcing_groups": [
            {
                "supplier_group_id": f"SUP-{material}",
                "material_number": material,
                "description": "Heavy duty tool",
                "total_quantity": qty,
                "unit": "EA",
                "standards": ["SANS 1028"],
                "brand_required": True,
                "datasheet_required": True,
                "sample_may_be_required": True,
                "buyer_requirement_row_ids": [f"ROW-{material}"],
                "buyer_line_indexes": [1],
            }
            for material, qty in [("327", 80), ("315", 50), ("302", 224), ("328", 280), ("1304", 40), ("316", 40)]
        ],
    }


def _email_model():
    return build_supplier_email_model(
        supplier={"supplier_name": "Sandbox Supplier", "supplier_email": "supplier@example.com"},
        requirement_pack=_pack(),
        request_id=REQUEST_ID,
        created_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        response_deadline="2026-07-19T08:00:00+00:00",
    )


def _request_context():
    return {
        "request_id": REQUEST_ID,
        "reference_number": "6000080579",
        "suppliers": [{"supplier_email": "supplier@example.com"}],
        "outbound_message_ids": ["<outbound@lmcp.test>"],
        "thread_ids": ["thread-1"],
    }


def test_mandatory_cc_cannot_be_removed_or_replaced():
    assert enforce_mandatory_cc([], {"supplier_rfq_cc": DEFAULT_MANDATORY_CC}) == [DEFAULT_MANDATORY_CC]
    assert enforce_mandatory_cc(["other@example.com", DEFAULT_MANDATORY_CC], {"supplier_rfq_cc": DEFAULT_MANDATORY_CC}) == [
        "other@example.com",
        DEFAULT_MANDATORY_CC,
    ]
    email = _email_model()
    assert email["from"] == DEFAULT_SUPPLIER_MAILBOX
    assert DEFAULT_MANDATORY_CC in email["cc"]


def test_at_least_three_supplier_requests_and_six_groups():
    suppliers = select_supplier_targets(minimum_supplier_target=3)
    assert len(suppliers) == 3
    email = _email_model()
    assert len(email["sourcing_items"]) == 6
    assert {str(item["material_number"]) for item in email["sourcing_items"]} >= {"327", "302", "328"}


def test_request_id_matching_and_ambiguous_rejection():
    message = {"subject": f"Re: {REQUEST_ID}", "body": "Buyer RFQ 6000080579", "from": "supplier@example.com"}
    match = match_supplier_response(message, _request_context())
    assert match["method"] == MATCH_REQUEST_ID_EXACT
    assert match["associated"] is True

    unrelated = {"subject": "Material 327 catalog", "body": "Material 327 available", "from": "other@example.com"}
    unrelated_match = match_supplier_response(unrelated, _request_context())
    assert unrelated_match["associated"] is False
    assert unrelated_match["method"] == "UNMATCHED"


def test_valid_quote_incomplete_decline_bounce_and_duplicate_classification(tmp_path):
    attachment_root = tmp_path / "attachments"
    seen_messages = set()
    seen_attachments = set()
    valid_msg = build_inbound_mime(
        from_addr="supplier@example.com",
        to_addr=DEFAULT_SUPPLIER_MAILBOX,
        cc=[DEFAULT_MANDATORY_CC],
        subject=f"Quote {REQUEST_ID}",
        body="\n".join([
            f"LMCP Request {REQUEST_ID}",
            "Supplier Legal Name: Supplier A",
            "Quotation Reference: Q1",
            "Quotation Date: 2026-07-17",
            "Validity: 30 days",
            "Delivery period: 7 days",
            "Material 327 unit price R1",
            "Material 315 unit price R1",
            "Material 302 unit price R1",
            "Material 328 unit price R1",
            "Material 1304 unit price R1",
            "Material 316 unit price R1",
            "Brand: Brand A",
        ]),
        message_id="<valid@lmcp.test>",
        attachments=[
            ("formal_quote.pdf", "application/pdf", b"%PDF quote"),
            ("datasheet.pdf", "application/pdf", b"%PDF datasheet"),
        ],
    )
    path = tmp_path / "valid.eml"
    path.write_bytes(valid_msg.as_bytes())
    parsed = parse_mime_message(path)
    manifest = capture_attachment_manifest(
        parsed,
        attachment_root=attachment_root,
        linked_sourcing_groups=["SUP-327"],
        seen_checksums=seen_attachments,
    )
    result = classify_supplier_response(parsed, _request_context(), manifest, seen_messages)
    assert result["response_status"] == VALID_SUPPLIER_QUOTATION

    duplicate = classify_supplier_response(parsed, _request_context(), manifest, seen_messages)
    assert duplicate["response_status"] == "DUPLICATE_RESPONSE"

    incomplete_msg = {"subject": f"Re {REQUEST_ID}", "body": f"LMCP Request {REQUEST_ID}\nAcknowledged only", "from": "supplier@example.com", "attachments": []}
    incomplete = classify_supplier_response(incomplete_msg, _request_context(), [], seen_messages)
    assert incomplete["response_status"] == SUPPLIER_RESPONSE_INCOMPLETE
    assert "six_item_prices" in incomplete["missing_fields"]

    decline = classify_supplier_response(
        {"subject": f"Re {REQUEST_ID}", "body": f"LMCP Request {REQUEST_ID}\nWe decline to quote", "from": "supplier@example.com", "attachments": []},
        _request_context(),
        [],
        seen_messages,
    )
    assert decline["response_status"] == SUPPLIER_DECLINED

    bounce = classify_supplier_response(
        {"subject": "Delivery Status Notification", "body": "Permanent failure", "from": "mailer-daemon@example.test", "attachments": []},
        _request_context(),
        [],
        seen_messages,
    )
    assert bounce["response_status"] == PERMANENT_BOUNCE


def test_attachment_checksum_duplicate_and_unsafe_rejection(tmp_path):
    msg = build_inbound_mime(
        from_addr="supplier@example.com",
        to_addr=DEFAULT_SUPPLIER_MAILBOX,
        cc=[DEFAULT_MANDATORY_CC],
        subject=f"Quote {REQUEST_ID}",
        body=f"LMCP Request {REQUEST_ID}",
        message_id="<attach@lmcp.test>",
        attachments=[
            ("datasheet.pdf", "application/pdf", b"same"),
            ("datasheet-copy.pdf", "application/pdf", b"same"),
            ("payload.exe", "application/x-msdownload", b"MZ"),
        ],
    )
    path = tmp_path / "attachments.eml"
    path.write_bytes(msg.as_bytes())
    manifest = capture_attachment_manifest(
        parse_mime_message(path),
        attachment_root=tmp_path / "attachments",
        linked_sourcing_groups=["SUP-327"],
        seen_checksums=set(),
    )
    assert all(item["checksum"] for item in manifest)
    assert any(item["duplicate"] for item in manifest)
    assert any(item["parsing_status"] == "REJECTED_UNSAFE_TYPE" for item in manifest)


def test_followup_eligibility_and_clarification_model():
    email = _email_model()
    due_time = datetime.fromisoformat(email["followup_due_at"])
    now = due_time + timedelta(hours=1)
    no_response = evaluate_followup_eligibility(initial_email=email, state="NO_RESPONSE", now=now, existing_followup_keys=set())
    assert no_response["followup_permitted"] is True
    valid = evaluate_followup_eligibility(initial_email=email, state=VALID_SUPPLIER_QUOTATION, now=now)
    assert valid["followup_permitted"] is False
    incomplete = evaluate_followup_eligibility(initial_email=email, state=SUPPLIER_RESPONSE_INCOMPLETE, now=now)
    assert incomplete["clarification_allowed"] is True
    declined = evaluate_followup_eligibility(initial_email=email, state=SUPPLIER_DECLINED, now=now)
    assert declined["followup_permitted"] is False
    bounced = evaluate_followup_eligibility(initial_email=email, state=PERMANENT_BOUNCE, now=now)
    assert bounced["replacement_supplier_recommended"] is True
    closed = evaluate_followup_eligibility(initial_email=email, state="NO_RESPONSE", now=now, buyer_closing_at=due_time)
    assert closed["reason"] == "buyer_rfq_closed"
    keys = set()
    first = evaluate_followup_eligibility(initial_email=email, state="NO_RESPONSE", now=now, existing_followup_keys=keys)
    second = evaluate_followup_eligibility(initial_email=email, state="NO_RESPONSE", now=now, existing_followup_keys=keys)
    assert first["followup_permitted"] is True
    assert second["reason"] == "duplicate_scheduler_execution_suppressed"
    clarification = build_clarification_email_model(
        initial_email=email,
        parsed_response={"from": "supplier@example.com", "message_id": "<msg@lmcp.test>"},
        missing_fields=["offered_brands", "delivery_period"],
    )
    assert DEFAULT_MANDATORY_CC in clarification["cc"]
    assert "offered_brands" in clarification["body"]


def test_no_response_pricing_continues_and_output_confinement(tmp_path):
    status = {"supplier_quote_coverage": "NO_VALID_QUOTES_FALLBACK_PRICING", "pricing_confidence": "fallback"}
    state = build_mailbox_validation_no_response_state(status)
    assert state["pricing_ready"] is True
    assert state["supplier_pricing_confirmed"] is False
    assert state["buyer_quote_preparation_allowed"] is True
    assert state["buyer_autonomous_submission_enabled"] is False
    assert safe_tmp_output_dir(tmp_path) == tmp_path.resolve()


def test_full_local_sandbox_validation_outputs_under_tmp(tmp_path):
    dry_run_path = Path("/tmp/lmcp-supplier-outreach-6000080579/outputs/supplier_outreach_dry_run.json")
    if not dry_run_path.exists():
        return
    output = tmp_path / "mailbox-validation"
    report = run_validation(dry_run_path=dry_run_path, output_root=output)
    assert report["result"] == "PASS"
    assert report["validation_mode"] == "LOCAL_MIME_SIMULATION"
    assert report["no_real_supplier_contacted"] is True
    assert report["live_email_sent"] is False
    assert (output / "reports" / "mailbox_validation_report.json").exists()
    assert all(str(path).startswith(str(output)) for path in output.rglob("*"))
