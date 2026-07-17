#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.gmail_draft_transport_service import (
    EmailTransportOperationBlocked,
    FakeGmailDraftClient,
    GmailAttachmentRequest,
    GmailDraftTransportService,
    build_supplier_gmail_draft_request,
    dataclass_to_dict,
)
from app.services.supplier_outreach_service import (
    DEFAULT_MANDATORY_CC,
    DEFAULT_SUPPLIER_MAILBOX,
    EMAIL_TYPE_CLARIFICATION,
    EMAIL_TYPE_FOLLOWUP_1,
    EMAIL_TYPE_INITIAL,
    RESPONSE_COVERAGE_NONE_FALLBACK,
    build_no_response_pricing_state,
)


DEFAULT_OUTREACH = Path("/tmp/lmcp-supplier-outreach-6000080579/outputs/supplier_outreach_dry_run.json")
DEFAULT_OUTPUT = Path("/tmp/lmcp-gmail-draft-transport-mock-6000080579")


class PersistentFakeGmailDraftClient(FakeGmailDraftClient):
    def __init__(self, state_path: Path):
        super().__init__()
        self.state_path = state_path
        if state_path.exists():
            data = json.loads(state_path.read_text(encoding="utf-8"))
            self._drafts = data.get("drafts") or {}
            self._by_idempotency = data.get("by_idempotency") or {}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({"drafts": self._drafts, "by_idempotency": self._by_idempotency}, indent=2), encoding="utf-8")

    def create_draft(self, *, user_id: str, raw_message: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        before = len(self._drafts)
        record = super().create_draft(user_id=user_id, raw_message=raw_message, metadata=metadata)
        if len(self._drafts) != before or record.get("duplicate_suppressed"):
            self._save()
        return record


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _safe_output(path: Path) -> Path:
    resolved = path.resolve()
    allowed = [Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(root in [resolved] + list(resolved.parents) for root in allowed):
        raise SystemExit(f"Refusing non-/tmp output path: {resolved}")
    return resolved


def _attachments(root: Path) -> List[GmailAttachmentRequest]:
    attachment_dir = root / "attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    files = [
        ("supplier_pricing_request_schedule.json", "application/json", b'{"controlled_test": true, "rfq": "6000080579"}', "pricing_request_schedule"),
        ("technical_requirements_summary.json", "application/json", b'{"standards": ["SANS 1028", "ISO 6787", "SANS 1211", "SANS 387"]}', "technical_requirements"),
        ("supplier_response_template.json", "application/json", b'{"fields": ["offered_brand", "unit_rate_ex_vat", "delivery_period"]}', "supplier_response_template"),
    ]
    out: List[GmailAttachmentRequest] = []
    for filename, mime_type, content, doc_type in files:
        path = attachment_dir / filename
        path.write_bytes(content)
        out.append(GmailAttachmentRequest(filename=filename, mime_type=mime_type, content=content, logical_document_type=doc_type).normalised())
    return out


def run_validation(*, outreach_path: Path, output_root: Path) -> Dict[str, Any]:
    output_root = _safe_output(output_root)
    for child in ["input", "mime", "audit", "reports", "state"]:
        (output_root / child).mkdir(parents=True, exist_ok=True)

    outreach = _read_json(outreach_path)
    emails = list(outreach.get("email_models") or [])
    if not emails:
        raise SystemExit("Supplier outreach model is missing.")
    source_email = emails[0]
    _write_json(output_root / "input" / "source_supplier_email_model_redacted.json", {
        "request_id": source_email.get("request_id"),
        "subject": source_email.get("subject"),
        "sourcing_item_count": len(source_email.get("sourcing_items") or []),
        "to": "controlled_test_recipient",
        "cc": DEFAULT_MANDATORY_CC,
    })

    env = {"LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY"}
    fake_client = PersistentFakeGmailDraftClient(output_root / "state" / "fake_gmail_drafts.json")
    initial_count = len(fake_client.list_drafts(user_id="me"))
    service = GmailDraftTransportService(gmail_client=fake_client, env=env, controlled_test_mode=True)
    attachments = _attachments(output_root)
    requests = [
        build_supplier_gmail_draft_request(source_email, recipient=DEFAULT_SUPPLIER_MAILBOX, email_type=EMAIL_TYPE_INITIAL, attachments=attachments),
        build_supplier_gmail_draft_request(source_email, recipient=DEFAULT_SUPPLIER_MAILBOX, email_type=EMAIL_TYPE_FOLLOWUP_1, attachments=attachments),
        build_supplier_gmail_draft_request(
            source_email,
            recipient=DEFAULT_SUPPLIER_MAILBOX,
            email_type=EMAIL_TYPE_CLARIFICATION,
            attachments=attachments,
            missing_fields=["offered_brand", "manufacturer_datasheet", "delivery_period", "formal_supplier_quotation"],
        ),
    ]

    draft_refs = [service.create_draft(request) for request in requests]
    duplicate = service.create_draft(requests[0])
    summaries = service.list_drafts()
    messages = [service.get_draft(ref) for ref in draft_refs]
    blocked: Dict[str, Any] = {}
    for operation, call in [
        ("send_email", lambda: service.send_email(requests[0])),
        ("send_draft", lambda: service.send_draft(draft_refs[0])),
        ("smtp_fallback_send", lambda: service.smtp_fallback_send(requests[0])),
        ("scheduler_dispatch", lambda: service.scheduler_dispatch(requests[0])),
    ]:
        try:
            call()
            blocked[operation] = {"blocked": False}
        except EmailTransportOperationBlocked as exc:
            blocked[operation] = {"blocked": True, **exc.to_dict()}

    for idx, message in enumerate(messages, start=1):
        _write_json(output_root / "mime" / f"draft_{idx}_summary.json", dataclass_to_dict(message.summary))
        _write_json(output_root / "mime" / f"draft_{idx}_message_redacted.json", {
            "reference": dataclass_to_dict(message.reference),
            "headers": message.decoded_headers,
            "body_contains_controlled_warning": "CONTROLLED GMAIL DRAFT-ONLY VALIDATION" in message.body_text,
            "attachment_manifest": message.attachment_manifest,
        })

    no_response = build_no_response_pricing_state({
        "supplier_quote_coverage": RESPONSE_COVERAGE_NONE_FALLBACK,
        "pricing_confidence": "controlled_fallback_requires_operator_review",
    })
    no_response["buyer_quote_preparation_allowed"] = True
    no_response["buyer_autonomous_submission_enabled"] = False
    checks = _checks(requests, messages, summaries, duplicate, blocked, no_response)
    audit = [
        service.audit_record(operation="create_draft", request=request, draft=ref)
        for request, ref in zip(requests, draft_refs)
    ]
    audit.extend(
        service.audit_record(operation=operation, request=requests[0], blocked=EmailTransportOperationBlocked(operation, "DRAFT_ONLY", data["reason"]))
        for operation, data in blocked.items()
        if data.get("blocked")
    )
    report = {
        "result": "PASS" if all(checks.values()) else "FAIL",
        "transport_mode": service.mode,
        "request_id": source_email.get("request_id"),
        "rfq_reference": "6000080579",
        "draft_count": len(summaries),
        "initial_draft_count": initial_count,
        "new_drafts_created": max(0, len(summaries) - initial_count),
        "canonical_drafts_reused": sum(1 for ref in draft_refs if ref.duplicate_suppressed),
        "duplicate_suppressed": duplicate.duplicate_suppressed,
        "drafts": [dataclass_to_dict(summary) for summary in summaries],
        "send_blocks": blocked,
        "no_response_pricing_state": no_response,
        "validation_checks": checks,
        "emails_sent": 0,
        "gmail_connected": False,
    }
    _write_json(output_root / "audit" / "gmail_draft_transport_audit.json", audit)
    _write_json(output_root / "reports" / "gmail_draft_transport_mock_report.json", report)
    _write_json(output_root / "reports" / "created_files.json", sorted(str(path) for path in output_root.rglob("*") if path.is_file()))
    return report


def _checks(requests, messages, summaries, duplicate, blocked, no_response):
    body = "\n".join(message.body_text for message in messages)
    return {
        "three_drafts_created": len(summaries) == 3,
        "mandatory_cc_enforced": all(DEFAULT_MANDATORY_CC in summary.cc for summary in summaries),
        "request_id_preserved": all(summary.supplier_request_id == "LMCP-SRFQ-6000080579-341E812698" for summary in summaries),
        "rfq_reference_preserved": all("6000080579" in summary.subject for summary in summaries),
        "six_sourcing_groups": all("Group | Material/Item Ref" in message.body_text for message in messages),
        "quantities_preserved": all(value in body for value in ["327 | Straight Pipe Wrench 350 mm Heavy Duty | 80", "302 | Club Hammer 1.8 kg", "328 | Straight Pipe Wrench 450 mm Heavy Duty | 280"]),
        "standards_preserved": all(value in body for value in ["SANS 1028", "ISO 6787", "SANS 1211", "SANS 387"]),
        "requirements_preserved": all(value in body for value in ["Offered brand required: True", "Manufacturer datasheet required: True", "Sample may be requested: True"]),
        "attachments_present": all(summary.attachment_count == 3 for summary in summaries),
        "duplicate_suppressed": duplicate.duplicate_suppressed is True,
        "direct_send_blocked": blocked["send_email"]["blocked"],
        "saved_draft_send_blocked": blocked["send_draft"]["blocked"],
        "smtp_fallback_blocked": blocked["smtp_fallback_send"]["blocked"],
        "scheduler_blocked": blocked["scheduler_dispatch"]["blocked"],
        "no_internal_pricing_disclosure": not any(term in body.lower() for term in ["gross profit", "markup", "margin on sales", "internal cost"]),
        "pricing_independent": no_response.get("pricing_ready") is True and no_response.get("buyer_autonomous_submission_enabled") is False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock Gmail draft-only transport validation for RFQ 6000080579.")
    parser.add_argument("--outreach", default=str(DEFAULT_OUTREACH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    report = run_validation(outreach_path=Path(args.outreach), output_root=Path(args.output))
    print(json.dumps({
        "result": report.get("result"),
        "transport_mode": report.get("transport_mode"),
        "draft_count": report.get("draft_count"),
        "new_drafts_created": report.get("new_drafts_created"),
        "canonical_drafts_reused": report.get("canonical_drafts_reused"),
        "duplicate_suppressed": report.get("duplicate_suppressed"),
        "checks_passed": sum(1 for ok in report.get("validation_checks", {}).values() if ok),
        "checks_total": len(report.get("validation_checks", {})),
        "emails_sent": report.get("emails_sent"),
        "gmail_connected": report.get("gmail_connected"),
    }, indent=2))
    return 0 if report.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
