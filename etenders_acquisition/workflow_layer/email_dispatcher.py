import os
import smtplib
from pathlib import Path
from email.message import EmailMessage


def send_email(
    to_email,
    subject,
    body,
    attachment_paths=None
):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_server or not smtp_username or not smtp_password:
        raise RuntimeError(
            "Missing SMTP settings. Set SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_username
    msg["To"] = to_email
    msg.set_content(body)

    for attachment_path in attachment_paths or []:
        path = Path(attachment_path)

        with open(path, "rb") as f:
            data = f.read()

        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=path.name
        )

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(msg)

    print(f"Email sent to {to_email}")
