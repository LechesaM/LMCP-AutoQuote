from __future__ import annotations

import os
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import QuoteDraft, Opportunity, SubmissionRecord
from app.email_utils import (
    build_submission_subject,
    build_submission_body,
    send_email_with_attachment,
)


COMPANY_NAME = os.getenv("COMPANY_NAME", "Lechesa Manaba Consulting and Projects (Pty) Ltd")
SENDER_EMAIL = os.getenv("SMTP_SENDER_EMAIL", os.getenv("SMTP_USERNAME", ""))

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"


def submit_quote_by_email(
    db: Session,
    quote_draft_id: int,
    recipient_email: str | None = None,
    cc_email: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    auto_use_opportunity_email: bool = True,
) -> SubmissionRecord:
    quote = db.query(QuoteDraft).filter(QuoteDraft.id == quote_draft_id).first()
    if not quote:
        raise ValueError("Quote draft not found.")

    opportunity = db.query(Opportunity).filter(Opportunity.id == quote.opportunity_id).first()
    if not opportunity:
        raise ValueError("Opportunity not found.")

    if not quote.pdf_path:
        raise ValueError("Quote draft does not have a PDF submission pack path.")

    if not os.path.exists(quote.pdf_path):
        raise ValueError(f"PDF submission pack file not found: {quote.pdf_path}")

    final_recipient = recipient_email
    if not final_recipient and auto_use_opportunity_email:
        final_recipient = opportunity.submission_email

    if not final_recipient:
        raise ValueError("No recipient email provided and no submission email exists on the opportunity.")

    final_subject = subject or build_submission_subject(
        company_name=COMPANY_NAME,
        tender_number=opportunity.tender_number,
        tender_title=opportunity.title,
        quote_number=quote.quote_number,
    )

    final_body = body or build_submission_body(
        company_name=COMPANY_NAME,
        tender_title=opportunity.title,
        tender_number=opportunity.tender_number,
    )

    record = SubmissionRecord(
        opportunity_id=opportunity.id,
        quote_draft_id=quote.id,
        recipient_email=final_recipient,
        cc_email=cc_email,
        subject=final_subject,
        body=final_body,
        attachment_path=quote.pdf_path,
        status="pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        message_id = send_email_with_attachment(
            smtp_host=SMTP_HOST,
            smtp_port=SMTP_PORT,
            smtp_username=SMTP_USERNAME,
            smtp_password=SMTP_PASSWORD,
            sender_email=SENDER_EMAIL,
            recipient_email=final_recipient,
            subject=final_subject,
            body=final_body,
            attachment_path=quote.pdf_path,
            cc_email=cc_email,
            use_tls=SMTP_USE_TLS,
        )

        record.status = "sent"
        record.sent_at = datetime.utcnow()
        record.message_id = message_id
        record.error_message = None

        quote.status = "submitted"

    except Exception as e:
        record.status = "failed"
        record.error_message = str(e)

    db.add(record)
    db.add(quote)
    db.commit()
    db.refresh(record)

    return record
