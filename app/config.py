from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.core.runtime_config import env as _env
from app.core.runtime_config import env_bool as _env_bool
from app.core.runtime_config import env_csv as _env_csv
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths


BASE_DIR = Path(__file__).resolve().parent.parent
runtime_config = get_runtime_config()
runtime_paths = get_runtime_paths()


def _normalize_scheme(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return "postgresql://" + raw_url[len("postgres://") :]
    return raw_url


def _replace_host(raw_url: str, new_host: str) -> str:
    parsed = urlparse(raw_url)

    username = parsed.username or ""
    password = parsed.password or ""
    auth = username
    if password:
        auth += f":{password}"

    netloc = f"{auth}@{new_host}" if auth else new_host
    if parsed.port:
        netloc += f":{parsed.port}"

    return urlunparse(parsed._replace(netloc=netloc))


def _ensure_connect_timeout(raw_url: str, seconds: int = 10) -> str:
    parsed = urlparse(raw_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("connect_timeout", str(seconds))
    return urlunparse(parsed._replace(query=urlencode(query)))


def _is_running_in_docker() -> bool:
    if Path("/.dockerenv").exists():
        return True
    for path in ("/proc/1/cgroup", "/proc/self/cgroup"):
        try:
            content = Path(path).read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if "docker" in content or "containerd" in content or "kubepods" in content:
            return True
    return False


def _derive_database_url() -> str:
    in_docker = _is_running_in_docker()

    db_user = _env("POSTGRES_USER") or _env("DB_USER")
    db_password = _env("POSTGRES_PASSWORD") or _env("DB_PASSWORD")
    db_name = _env("POSTGRES_DB") or _env("DB_NAME")
    db_port = _env("DB_PORT", "5432")
    docker_host = _env("DB_DOCKER_HOST", _env("DB_HOST", "db"))
    local_host = _env("DB_LOCAL_HOST", _env("DB_HOST", "localhost"))

    raw_url = ""
    if db_user and db_password and db_name:
        host = docker_host if in_docker else local_host
        raw_url = f"postgresql://{db_user}:{db_password}@{host}:{db_port}/{db_name}"

    if not raw_url and in_docker:
        raw_url = _env("DATABASE_URL") or _env("SQLALCHEMY_DATABASE_URL")
    if not raw_url and not in_docker:
        raw_url = _env("DATABASE_URL_LOCAL") or _env("DATABASE_URL") or _env("SQLALCHEMY_DATABASE_URL")

    if not raw_url:
        default_host = "db" if in_docker else "localhost"
        raw_url = f"postgresql://postgres:postgres@{default_host}:5432/lmcp_autoquote"

    raw_url = _normalize_scheme(raw_url)

    parsed = urlparse(raw_url)
    current_host = (parsed.hostname or "").strip().lower()
    docker_hosts = {"postgres", "db", "database", "lmcp-db", "postgresql"}
    local_hosts = {"localhost", "127.0.0.1", "0.0.0.0", ""}

    if not in_docker and current_host in docker_hosts:
        raw_url = _replace_host(raw_url, local_host)
    if in_docker and current_host in local_hosts | {"postgres"}:
        raw_url = _replace_host(raw_url, docker_host)

    return _ensure_connect_timeout(raw_url, 10)


@dataclass(frozen=True)
class Settings:
    app_name: str = "LMCP AutoQuote System"
    app_version: str = _env("LMCP_APP_VERSION", "2.6.0-manual-production")
    environment: str = _env("LMCP_ENV", _env("ENVIRONMENT", "development")).lower()
    production_mode: str = runtime_config.mode.value
    debug: bool = _env_bool("LMCP_DEBUG", False)
    secret_key: str = _env("LMCP_SECRET_KEY", _env("SECRET_KEY", "lmcp-dev-secret"))
    cors_origins: Tuple[str, ...] = field(default_factory=lambda: _env_csv("LMCP_CORS_ORIGINS", "*"))

    base_dir: Path = BASE_DIR
    project_root: Path = runtime_paths.project_root
    runtime_dir: Path = runtime_paths.runtime_root
    monthly_quotes_dir: Path = runtime_paths.downloads_dir
    log_dir: Path = runtime_paths.logs_dir
    handwriting_runtime_dir: Path = runtime_paths.handwriting_runtime_dir
    tender_form_runtime_dir: Path = runtime_paths.tender_form_runtime_dir
    clickable_navigation_runtime_dir: Path = runtime_paths.clickable_navigation_runtime_dir
    submission_proofs_dir: Path = runtime_paths.proofs_dir
    portal_submission_dir: Path = runtime_paths.submissions_dir
    final_submission_dir: Path = runtime_paths.final_submission_dir
    proof_center_dir: Path = runtime_paths.proof_center_dir
    manual_production_dir: Path = runtime_paths.manual_production_dir
    temp_dir: Path = runtime_paths.temp_dir
    exports_dir: Path = runtime_paths.exports_dir
    operator_auth_db_path: Path = runtime_paths.operator_auth_db_path
    operator_session_cookie_name: str = _env("LMCP_OPERATOR_SESSION_COOKIE_NAME", "lmcp_operator_session")
    operator_session_timeout_seconds: int = max(300, int(_env("LMCP_OPERATOR_SESSION_TIMEOUT_SECONDS", "28800") or "28800"))
    operator_session_cookie_secure: bool = _env_bool("LMCP_OPERATOR_SESSION_COOKIE_SECURE", False)
    operator_auth_allow_dev_fallback: bool = _env_bool("LMCP_OPERATOR_AUTH_ALLOW_DEV_FALLBACK", False)

    database_url: str = field(default_factory=_derive_database_url)
    redis_url: str = _env("REDIS_URL", "redis://localhost:6379/0")
    ocds_base_url: str = _env("OCDS_BASE_URL", "https://ocds-api.etenders.gov.za/api")
    poll_page_size: int = int(_env("POLL_PAGE_SIZE", "200"))
    poll_lookback_days: int = int(_env("POLL_LOOKBACK_DAYS", "3"))
    soe_allowlist: Tuple[str, ...] = field(default_factory=lambda: _env_csv("SOE_ALLOWLIST"))
    delivery_keywords: Tuple[str, ...] = field(default_factory=lambda: _env_csv("DELIVERY_KEYWORDS", "supply and delivery,delivery,supply"))

    your_company_name: str = _env("YOUR_COMPANY_NAME", "Your Company (Pty) Ltd")
    your_contact_email: str = _env("YOUR_CONTACT_EMAIL", "info@example.com")
    your_contact_phone: str = _env("YOUR_CONTACT_PHONE", "")
    your_location: str = _env("YOUR_LOCATION", "")
    email_tone: str = _env("EMAIL_TONE", "professional")

    send_enabled: bool = _env_bool("SEND_ENABLED", False)
    smtp_host: str = _env("SMTP_HOST", "")
    smtp_port: int = int(_env("SMTP_PORT", "587"))
    smtp_user: str = _env("SMTP_USER", "")
    smtp_pass: str = _env("SMTP_PASS", "")
    smtp_tls: bool = _env_bool("SMTP_TLS", True)
    mail_from: str = _env("MAIL_FROM", _env("YOUR_CONTACT_EMAIL", "info@example.com"))
    require_rfp_email_allowed: bool = _env_bool("REQUIRE_RFP_EMAIL_ALLOWED", True)
    max_sends_per_day: int = int(_env("MAX_SENDS_PER_DAY", "20"))

    target_country: str = "South Africa"
    target_categories: Tuple[str, ...] = ("supply", "delivery")
    excluded_tender_segments: Tuple[str, ...] = (
        "medical consumables",
        "it equipment",
        "petrol",
        "diesel",
        "catering",
        "compulsory briefing sessions",
    )
    minimum_profit_margin_zar: float = float(_env("LMCP_MIN_PROFIT_ZAR", "30000"))
    minimum_supply_margin_ratio: float = float(_env("LMCP_MIN_SUPPLY_MARGIN_RATIO", "0.25"))
    final_submit_manual_only: bool = True
    require_buyer_pricing_schedule_completion: bool = True
    manual_production_enforced: bool = runtime_config.manual_production_enforced
    enable_legacy_routers: bool = runtime_config.enable_legacy_routers
    allow_degraded_startup: bool = runtime_config.allow_degraded_startup
    runtime_safety_enabled: bool = runtime_config.runtime_safety_enabled
    strict_production_startup: bool = runtime_config.strict_production_startup

    def ensure_directories(self) -> None:
        runtime_paths.ensure_directories()

    def configure_environment(self) -> None:
        runtime_config.configure_environment()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config = Settings()
    config.configure_environment()
    config.ensure_directories()
    return config


settings = get_settings()
