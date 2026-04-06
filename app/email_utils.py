from __future__ import annotations

import os
import mimetypes
import smtplib
from email.message import EmailMessage
from typing import Optional


def build_submission_subject(company_name: str, tender_number: str | None, tender_title: str, quote_number: str) -> str:
    tender_ref = tender_number or "Tender Submission"
    return f"{company_name} Submission - {tender_ref} - {quote_number}"


def build_submission_body(
    company_name: str,
    tender_title: str,
    tender_number: str | None,
    contact_name: str | None = None,
) -> str:
    greeting = f"Dear {contact_name}," if contact_name else "Dear Sir/Madam,"
    tender_ref = tender_number or "N/A"

    return f"""{greeting}

Please find attached our submission for the following opportunity:

Tender / RFQ Number: {tender_ref}
Tender Title: {tender_title}
Submitting Company: {company_name}

Kindly confirm receipt of this submission.

Regards,
{company_name}
"""


def send_email_with_attachment(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    attachment_path: str,
    cc_email: Optional[str] = None,
    use_tls: bool = True,
) -> str:
    if not os.path.exists(attachment_path):
        raise FileNotFoundError(f"Attachment not found: {attachment_path}")

    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject

    if cc_email:
        msg["Cc"] = cc_email

    msg.set_content(body)

    content_type, encoding = mimetypes.guess_type(attachment_path)
    if content_type is None or encoding is not None:
        content_type = "application/octet-stream"

    maintype, subtype = content_type.split("/", 1)

    with open(attachment_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype=maintype,
            subtype=subtype,
            filename=os.path.basename(attachment_path),
        )

    recipients = [recipient_email]
    if cc_email:
        recipients.extend([x.strip() for x in cc_email.split(",") if x.strip()])

    with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
        if use_tls:
            server.starttls()
        if smtp_username:
            server.login(smtp_username, smtp_password)
        server.send_message(msg, from_addr=sender_email, to_addrs=recipients)

    return msg.get("Message-ID", "")
