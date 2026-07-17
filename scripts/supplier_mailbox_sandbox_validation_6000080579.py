#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.supplier_mailbox_sandbox_service import (
    PERMANENT_BOUNCE,
    SUPPLIER_DECLINED,
    SUPPLIER_RESPONSE_INCOMPLETE,
    VALID_SUPPLIER_QUOTATION,
    build_clarification_email_model,
    build_inbound_mime,
    build_mailbox_audit_event,
    build_mailbox_validation_no_response_state,
    build_outbound_mime,
    build_sandbox_status,
    capture_attachment_manifest,
    classify_supplier_response,
    evaluate_followup_eligibility,
    parse_mime_message,
    safe_tmp_output_dir,
    write_json,
)
from app.services.supplier_outreach_service import DEFAULT_MANDATORY_CC, DEFAULT_SUPPLIER_MAILBOX


DEFAULT_DRY_RUN = Path("/tmp/lmcp-supplier-outreach-6000080579/outputs/supplier_outreach_dry_run.json")
DEFAULT_OUTPUT = Path("/tmp/lmcp-supplier-mailbox-validation-6000080579")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_eml(path: Path, message) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(message.as_bytes())


def _attachment_payloads() -> List:
    return [
        ("formal_quote_6000080579.pdf", "application/pdf", b"%PDF-1.4 sandbox formal supplier quote\n"),
        ("manufacturer_datasheet_pipe_wrench.pdf", "application/pdf", b"%PDF-1.4 sandbox manufacturer datasheet\n"),
        ("product_sheet.png", "image/png", b"\x89PNG\r\n\x1a\nsandbox image payload\n"),
        (
            "pricing_schedule.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PK\x03\x04 sandbox spreadsheet pricing schedule\n",
        ),
        ("compliance_certificate.pdf", "application/pdf", b"%PDF-1.4 sandbox compliance certificate\n"),
        ("manufacturer_datasheet_pipe_wrench_duplicate.pdf", "application/pdf", b"%PDF-1.4 sandbox manufacturer datasheet\n"),
        ("unsafe_payload.exe", "application/x-msdownload", b"MZ sandbox unsafe executable\n"),
    ]


def _valid_quote_body(request_id: str) -> str:
    items = [
        ("327", "PipeMaster HD", "ToolCo", "PM-327", "850.00"),
        ("315", "AdjustPro", "ToolCo", "ADJ-315", "320.00"),
        ("302", "HammerPro", "ToolCo", "HAM-302", "260.00"),
        ("328", "PipeMaster XL", "ToolCo", "PM-328", "1150.00"),
        ("1304", "ChiselPro", "ToolCo", "CH-1304", "180.00"),
        ("316", "AdjustPro XL", "ToolCo", "ADJ-316", "420.00"),
    ]
    lines = [
        f"LMCP Request {request_id}",
        "Buyer RFQ 6000080579",
        "Supplier Legal Name: Sandbox Tools Supplier A (Pty) Ltd",
        "Quotation Reference: Q-SANDBOX-6000080579-A",
        "Quotation Date: 2026-07-17",
        "Validity: 30 days",
        "Delivery period: 7 working days",
        "Delivery cost: R12000.00",
        "Stock: Available subject to final confirmation",
        "Warranty: 12 months manufacturer warranty",
        "VAT: 15%",
        "Contact person: Sandbox Contact",
    ]
    for material, brand, manufacturer, model, price in items:
        lines.extend([
            f"Material {material} unit price R{price}",
            f"Brand: {brand}",
            f"Manufacturer: {manufacturer}",
            f"Model: {model}",
        ])
    lines.extend([
        "Total excluding VAT: R500240.00",
        "Total including VAT: R575276.00",
        "Compliance confirmation: SANS and ISO evidence attached where applicable.",
    ])
    return "\n".join(lines)


def _incomplete_body(request_id: str) -> str:
    return "\n".join([
        f"LMCP Request {request_id}",
        "Buyer RFQ 6000080579",
        "Supplier Legal Name: Sandbox Industrial Supplies B",
        "Quotation Reference: ACK-6000080579-B",
        "We acknowledge receipt and can possibly assist with some items.",
        "Material 327 unit price R900.00",
        "Please advise if brand details can follow later.",
    ])


def _decline_body(request_id: str) -> str:
    return "\n".join([
        f"LMCP Request {request_id}",
        "Buyer RFQ 6000080579",
        "We decline this request and are unable to quote before the deadline.",
    ])


def _bounce_body(to_addr: str) -> str:
    return "\n".join([
        "Delivery Status Notification",
        "Permanent failure",
        f"The message to {to_addr} could not be delivered.",
    ])


def _request_context(dry_run: Dict[str, Any], outbound_records: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "request_id": dry_run.get("request_id"),
        "reference_number": "6000080579",
        "suppliers": dry_run.get("suppliers") or [],
        "outbound_message_ids": [item["message_id"] for item in outbound_records],
        "thread_ids": [item["thread_id"] for item in outbound_records],
    }


def run_validation(*, dry_run_path: Path, output_root: Path) -> Dict[str, Any]:
    output_root = safe_tmp_output_dir(output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    for child in ["outbound", "inbound", "attachments", "parsed", "audit", "reports"]:
        (output_root / child).mkdir(parents=True, exist_ok=True)

    dry_run = _read_json(dry_run_path)
    emails = list(dry_run.get("email_models") or [])
    if len(emails) < 3:
        raise SystemExit("Dry-run supplier email model does not contain three suppliers.")

    request_id = str(dry_run.get("request_id"))
    outbound_records: List[Dict[str, str]] = []
    for index, email in enumerate(emails[:3], start=1):
        message_id = f"<sandbox-outbound-{index}-{request_id}@lmcp.test>"
        thread_id = f"thread-{request_id}-{index}"
        msg = build_outbound_mime(email, message_id=message_id, thread_id=thread_id)
        path = output_root / "outbound" / f"initial_request_{index}.eml"
        _write_eml(path, msg)
        outbound_records.append({
            "path": str(path),
            "message_id": message_id,
            "thread_id": thread_id,
            "supplier_email": str(email.get("to")),
        })

    request_context = _request_context(dry_run, outbound_records)
    supplier_a = emails[0]["to"]
    supplier_b = emails[1]["to"]
    supplier_c = emails[2]["to"]
    inbound_specs = [
        (
            "valid_supplier_quote.eml",
            build_inbound_mime(
                from_addr=supplier_a,
                to_addr=DEFAULT_SUPPLIER_MAILBOX,
                cc=[DEFAULT_MANDATORY_CC],
                subject=f"Re: Supplier RFQ | Buyer RFQ 6000080579 | LMCP Request {request_id}",
                body=_valid_quote_body(request_id),
                message_id=f"<sandbox-valid-{request_id}@lmcp.test>",
                thread_id=outbound_records[0]["thread_id"],
                in_reply_to=outbound_records[0]["message_id"],
                attachments=_attachment_payloads(),
            ),
        ),
        (
            "incomplete_supplier_response.eml",
            build_inbound_mime(
                from_addr=supplier_b,
                to_addr=DEFAULT_SUPPLIER_MAILBOX,
                cc=[DEFAULT_MANDATORY_CC],
                subject="Re: RFQ 6000080579 acknowledgement",
                body=_incomplete_body(request_id),
                message_id=f"<sandbox-incomplete-{request_id}@lmcp.test>",
                thread_id=outbound_records[1]["thread_id"],
                in_reply_to=outbound_records[1]["message_id"],
                attachments=[],
            ),
        ),
        (
            "unrelated_email.eml",
            build_inbound_mime(
                from_addr="unrelated@example.com",
                to_addr=DEFAULT_SUPPLIER_MAILBOX,
                cc=[],
                subject="Catalog update material 327",
                body="This unrelated mail mentions material 327 but has no request ID, no RFQ reference, and no thread.",
                message_id="<sandbox-unrelated@lmcp.test>",
                attachments=[],
            ),
        ),
        (
            "duplicate_supplier_quote.eml",
            build_inbound_mime(
                from_addr=supplier_a,
                to_addr=DEFAULT_SUPPLIER_MAILBOX,
                cc=[DEFAULT_MANDATORY_CC],
                subject=f"Re: Supplier RFQ | Buyer RFQ 6000080579 | LMCP Request {request_id}",
                body=_valid_quote_body(request_id),
                message_id=f"<sandbox-valid-{request_id}@lmcp.test>",
                thread_id=outbound_records[0]["thread_id"],
                in_reply_to=outbound_records[0]["message_id"],
                attachments=_attachment_payloads(),
            ),
        ),
        (
            "bounce_notification.eml",
            build_inbound_mime(
                from_addr="mailer-daemon@example.test",
                to_addr=DEFAULT_SUPPLIER_MAILBOX,
                cc=[],
                subject="Delivery Status Notification (Permanent Failure)",
                body=_bounce_body(supplier_c),
                message_id=f"<sandbox-bounce-{request_id}@lmcp.test>",
                thread_id=outbound_records[2]["thread_id"],
                in_reply_to=outbound_records[2]["message_id"],
                attachments=[],
            ),
        ),
        (
            "supplier_decline.eml",
            build_inbound_mime(
                from_addr=supplier_c,
                to_addr=DEFAULT_SUPPLIER_MAILBOX,
                cc=[DEFAULT_MANDATORY_CC],
                subject=f"Re: Supplier RFQ | Buyer RFQ 6000080579 | LMCP Request {request_id}",
                body=_decline_body(request_id),
                message_id=f"<sandbox-decline-{request_id}@lmcp.test>",
                thread_id=outbound_records[2]["thread_id"],
                in_reply_to=outbound_records[2]["message_id"],
                attachments=[],
            ),
        ),
    ]

    inbound_paths: List[Path] = []
    for filename, message in inbound_specs:
        path = output_root / "inbound" / filename
        _write_eml(path, message)
        inbound_paths.append(path)

    seen_message_keys = set()
    seen_attachment_checksums = set()
    processed: List[Dict[str, Any]] = []
    audit_events: List[Dict[str, Any]] = []
    for path in inbound_paths:
        parsed = parse_mime_message(path)
        attachment_manifest = capture_attachment_manifest(
            parsed,
            attachment_root=output_root / "attachments",
            linked_sourcing_groups=[str(item.get("supplier_group_id")) for item in emails[0].get("sourcing_items") or []],
            seen_checksums=seen_attachment_checksums,
            received_at=datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc),
        )
        response = classify_supplier_response(parsed, request_context, attachment_manifest, seen_message_keys)
        processed.append({
            "source_file": str(path),
            "parsed_message": {k: v for k, v in parsed.items() if k != "attachments"},
            "attachment_manifest": attachment_manifest,
            "response": response,
        })
        audit_events.append(build_mailbox_audit_event(
            request_id=request_id,
            rfq_id="TEMP-RFQ-6000080579",
            message=parsed,
            response_status=response.get("response_status"),
            matching=response.get("matching") or {},
            attachment_manifest=attachment_manifest,
            event_type=response.get("response_status"),
        ))

    valid_response = _find(processed, VALID_SUPPLIER_QUOTATION)
    incomplete_response = _find(processed, SUPPLIER_RESPONSE_INCOMPLETE)
    first_due_raw = emails[0].get("followup_due_at") or "2026-07-19T10:00:00+00:00"
    first_due = datetime.fromisoformat(str(first_due_raw).replace("Z", "+00:00"))
    now = first_due + timedelta(hours=1)
    existing_followup_keys = set()
    followup_results = {
        "no_response": evaluate_followup_eligibility(initial_email=emails[0], state="NO_RESPONSE", now=now, existing_followup_keys=existing_followup_keys),
        "valid_response": evaluate_followup_eligibility(initial_email=emails[0], state=VALID_SUPPLIER_QUOTATION, now=now),
        "incomplete_response": evaluate_followup_eligibility(initial_email=emails[1], state=SUPPLIER_RESPONSE_INCOMPLETE, now=now),
        "decline": evaluate_followup_eligibility(initial_email=emails[2], state=SUPPLIER_DECLINED, now=now),
        "bounce": evaluate_followup_eligibility(initial_email=emails[2], state=PERMANENT_BOUNCE, now=now),
        "closed_rfq": evaluate_followup_eligibility(
            initial_email=emails[0],
            state="NO_RESPONSE",
            now=now,
            buyer_closing_at=datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc),
        ),
        "duplicate_scheduler_first": None,
        "duplicate_scheduler_second": None,
    }
    duplicate_keys = set()
    followup_results["duplicate_scheduler_first"] = evaluate_followup_eligibility(initial_email=emails[0], state="NO_RESPONSE", now=now, existing_followup_keys=duplicate_keys)
    followup_results["duplicate_scheduler_second"] = evaluate_followup_eligibility(initial_email=emails[0], state="NO_RESPONSE", now=now, existing_followup_keys=duplicate_keys)
    clarification_model = build_clarification_email_model(
        initial_email=emails[1],
        parsed_response=incomplete_response.get("parsed_message") if incomplete_response else {},
        missing_fields=((incomplete_response.get("response") or {}).get("missing_fields") or []),
    )

    sandbox_status = build_sandbox_status(
        supplier_count=3,
        minimum_supplier_target=3,
        valid_quotes_received=1,
        declined_requests=1,
        bounced_requests=1,
        followups_due=1,
    )
    no_response_state = build_mailbox_validation_no_response_state(sandbox_status)
    report = {
        "validation_mode": "LOCAL_MIME_SIMULATION",
        "request_id": request_id,
        "rfq_reference": "6000080579",
        "no_real_supplier_contacted": True,
        "live_email_sent": False,
        "recipients_simulated_only": [email.get("to") for email in emails[:3]],
        "from_address": DEFAULT_SUPPLIER_MAILBOX,
        "mandatory_cc": DEFAULT_MANDATORY_CC,
        "outbound_records": outbound_records,
        "response_results": {
            Path(item["source_file"]).stem: item["response"] for item in processed
        },
        "followup_results": followup_results,
        "clarification_model": clarification_model,
        "no_response_pricing_state": no_response_state,
        "audit_event_count": len(audit_events),
        "attachment_count": sum(len(item["attachment_manifest"]) for item in processed),
        "validation_checks": _validation_checks(emails, processed, followup_results, no_response_state, clarification_model),
    }
    report["result"] = "PASS" if all(report["validation_checks"].values()) else "FAIL"

    write_json(output_root / "parsed" / "response_processing_results.json", processed)
    write_json(output_root / "parsed" / "valid_supplier_quote.json", valid_response or {})
    write_json(output_root / "parsed" / "incomplete_supplier_response.json", incomplete_response or {})
    write_json(output_root / "audit" / "mailbox_audit_events.json", audit_events)
    write_json(output_root / "reports" / "mailbox_validation_report.json", report)
    write_json(output_root / "reports" / "followup_eligibility_report.json", followup_results)
    write_json(output_root / "reports" / "no_response_pricing_state.json", no_response_state)
    write_json(output_root / "reports" / "attachment_manifest.json", [a for item in processed for a in item["attachment_manifest"]])
    write_json(output_root / "reports" / "created_files.json", sorted(str(path) for path in output_root.rglob("*") if path.is_file()))
    return report


def _find(processed: Sequence[Dict[str, Any]], status: str) -> Dict[str, Any]:
    for item in processed:
        if (item.get("response") or {}).get("response_status") == status:
            return item
    return {}


def _validation_checks(
    emails: Sequence[Dict[str, Any]],
    processed: Sequence[Dict[str, Any]],
    followups: Dict[str, Any],
    no_response_state: Dict[str, Any],
    clarification_model: Dict[str, Any],
) -> Dict[str, bool]:
    statuses = {Path(item["source_file"]).stem: (item.get("response") or {}).get("response_status") for item in processed}
    valid = _find(processed, VALID_SUPPLIER_QUOTATION)
    valid_attachments = valid.get("attachment_manifest") or []
    return {
        "mandatory_cc_initial": all(DEFAULT_MANDATORY_CC in (email.get("cc") or []) for email in emails[:3]),
        "minimum_three_requests": len(emails) >= 3,
        "request_contains_six_groups": all(len(email.get("sourcing_items") or []) == 6 for email in emails[:3]),
        "valid_quotation_recognised": statuses.get("valid_supplier_quote") == VALID_SUPPLIER_QUOTATION,
        "incomplete_response_recognised": statuses.get("incomplete_supplier_response") == SUPPLIER_RESPONSE_INCOMPLETE,
        "unrelated_unmatched": statuses.get("unrelated_email") == "UNRELATED_EMAIL",
        "duplicate_detected": statuses.get("duplicate_supplier_quote") == "DUPLICATE_RESPONSE",
        "bounce_detected": statuses.get("bounce_notification") == "PERMANENT_BOUNCE",
        "decline_detected": statuses.get("supplier_decline") == "SUPPLIER_DECLINED",
        "attachments_checksummed": all(bool(item.get("checksum")) for item in valid_attachments),
        "unsafe_attachment_rejected": any(item.get("parsing_status") == "REJECTED_UNSAFE_TYPE" for item in valid_attachments),
        "duplicate_attachment_detected": any(item.get("duplicate") for item in valid_attachments),
        "no_response_followup_due": bool((followups.get("no_response") or {}).get("followup_permitted")),
        "valid_response_suppresses_followup": not bool((followups.get("valid_response") or {}).get("followup_permitted")),
        "incomplete_prepares_clarification": bool((followups.get("incomplete_response") or {}).get("clarification_allowed")),
        "decline_suppresses_followup": not bool((followups.get("decline") or {}).get("followup_permitted")),
        "bounce_suppresses_followup": not bool((followups.get("bounce") or {}).get("followup_permitted")),
        "closed_rfq_suppresses_followup": not bool((followups.get("closed_rfq") or {}).get("followup_permitted")),
        "duplicate_scheduler_suppressed": not bool((followups.get("duplicate_scheduler_second") or {}).get("followup_permitted")),
        "clarification_cc_enforced": DEFAULT_MANDATORY_CC in (clarification_model.get("cc") or []),
        "pricing_continues_zero_responses": no_response_state.get("pricing_ready") is True and no_response_state.get("buyer_quote_preparation_allowed") is True,
        "buyer_autonomous_submission_disabled": no_response_state.get("buyer_autonomous_submission_enabled") is False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Local MIME supplier mailbox sandbox validation for RFQ 6000080579.")
    parser.add_argument("--dry-run", default=str(DEFAULT_DRY_RUN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    report = run_validation(dry_run_path=Path(args.dry_run), output_root=Path(args.output))
    print(json.dumps({
        "result": report.get("result"),
        "request_id": report.get("request_id"),
        "validation_mode": report.get("validation_mode"),
        "checks_passed": sum(1 for ok in (report.get("validation_checks") or {}).values() if ok),
        "checks_total": len(report.get("validation_checks") or {}),
        "live_email_sent": report.get("live_email_sent"),
        "no_real_supplier_contacted": report.get("no_real_supplier_contacted"),
    }, indent=2))
    return 0 if report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
