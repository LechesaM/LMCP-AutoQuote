import smtplib
from email.message import EmailMessage
from app.config import settings

def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.send_enabled:
        raise RuntimeError("SEND_ENABLED=false (sending disabled)")

    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST not configured")

    msg = EmailMessage()
    msg["From"] = settings.mail_from or settings.smtp_user or settings.your_contact_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if settings.smtp_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
