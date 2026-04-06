import os
from dataclasses import dataclass

def _csv(name: str, default: str = "") -> list[str]:
    v = os.getenv(name, default)
    return [x.strip() for x in v.split(",") if x.strip()]

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/autoquote")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    ocds_base_url: str = os.getenv("OCDS_BASE_URL", "https://ocds-api.etenders.gov.za/api")
    poll_page_size: int = int(os.getenv("POLL_PAGE_SIZE", "200"))
    poll_lookback_days: int = int(os.getenv("POLL_LOOKBACK_DAYS", "3"))

    soe_allowlist: list[str] = tuple(_csv("SOE_ALLOWLIST"))
    delivery_keywords: list[str] = tuple(_csv("DELIVERY_KEYWORDS"))

    your_company_name: str = os.getenv("YOUR_COMPANY_NAME", "Your Company (Pty) Ltd")
    your_contact_email: str = os.getenv("YOUR_CONTACT_EMAIL", "info@example.com")
    your_contact_phone: str = os.getenv("YOUR_CONTACT_PHONE", "")
    your_location: str = os.getenv("YOUR_LOCATION", "")
    email_tone: str = os.getenv("EMAIL_TONE", "professional")


    # Sending (prototype: OFF by default)
    send_enabled: bool = os.getenv("SEND_ENABLED", "false").lower() in ("1","true","yes","y")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_pass: str = os.getenv("SMTP_PASS", "")
    smtp_tls: bool = os.getenv("SMTP_TLS", "true").lower() in ("1","true","yes","y")
    mail_from: str = os.getenv("MAIL_FROM", your_contact_email if 'your_contact_email' in locals() else os.getenv("YOUR_CONTACT_EMAIL","info@example.com"))

    require_rfp_email_allowed: bool = os.getenv("REQUIRE_RFP_EMAIL_ALLOWED", "true").lower() in ("1","true","yes","y")
    max_sends_per_day: int = int(os.getenv("MAX_SENDS_PER_DAY", "20"))


settings = Settings()
