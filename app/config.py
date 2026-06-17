from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _env_csv(name: str, default: str = "") -> Tuple[str, ...]:
    raw = _env(name, default)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


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
    # SQLite URLs do not accept the same query normalization as networked DB URLs.
    # Leave them untouched so local file-backed test databases remain valid.
    if raw_url.startswith("sqlite:"):
        return raw_url
    parsed = urlparse(raw_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("connect_timeout", str(seconds))
    return urlunparse(parsed._replace(query=urlencode(query)))


def _sqlite_database_url() -> str:
    raw_path = _env(
        "LMCP_MANUAL_PRODUCTION_DB_PATH",
        str(BASE_DIR / "runtime" / "manual_production" / "lmcp_operations.db"),
    )
    db_path = Path(raw_path).expanduser()
    if not db_path.is_absolute():
        db_path = (BASE_DIR / db_path).resolve()
    else:
        db_path = db_path.resolve()
    return f"sqlite:///{db_path.as_posix()}"


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
    backend = _env("LMCP_DB_BACKEND", "sqlite").lower()
    if backend == "sqlite":
        return _sqlite_database_url()

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

    if raw_url.startswith("sqlite:"):
        return raw_url

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
    debug: bool = _env_bool("LMCP_DEBUG", False)
    secret_key: str = _env("LMCP_SECRET_KEY", _env("SECRET_KEY", "lmcp-dev-secret"))
    cors_origins: Tuple[str, ...] = field(default_factory=lambda: _env_csv("LMCP_CORS_ORIGINS", "*"))

    base_dir: Path = BASE_DIR
    project_root: Path = Path(_env("LMCP_PROJECT_ROOT", _env("PROJECT_ROOT", str(BASE_DIR)))).expanduser().resolve()
    runtime_dir: Path = Path(
        _env(
            "LMCP_RUNTIME_DIR",
            _env("RUNTIME_DIR", _env("SUPPLY_COMMAND_RUNTIME", _env("DATA_DIR", str(BASE_DIR / "runtime")))),
        )
    ).expanduser().resolve()
    monthly_quotes_dir: Path = Path(_env("LMCP_MONTHLY_QUOTES_DIR", str(BASE_DIR / "monthly_quotes"))).expanduser().resolve()
    log_dir: Path = Path(_env("LMCP_LOG_DIR", str(BASE_DIR / "runtime" / "logs"))).expanduser().resolve()
    handwriting_runtime_dir: Path = Path(_env("LMCP_HANDWRITING_RUNTIME_DIR", str(BASE_DIR / "runtime" / "handwriting_simulation"))).expanduser().resolve()
    tender_form_runtime_dir: Path = Path(_env("LMCP_TENDER_FORM_RUNTIME_DIR", str(BASE_DIR / "runtime" / "tender_form_intelligence"))).expanduser().resolve()
    clickable_navigation_runtime_dir: Path = Path(_env("LMCP_CLICKABLE_NAVIGATION_RUNTIME_DIR", str(BASE_DIR / "runtime" / "clickable_navigation_v40"))).expanduser().resolve()
    submission_proofs_dir: Path = Path(_env("LMCP_SUBMISSION_PROOFS_DIR", str(BASE_DIR / "runtime" / "submission_proofs"))).expanduser().resolve()
    portal_submission_dir: Path = Path(_env("LMCP_PORTAL_SUBMISSION_DIR", str(BASE_DIR / "runtime" / "portal_submission"))).expanduser().resolve()
    final_submission_dir: Path = Path(_env("LMCP_FINAL_SUBMISSION_DIR", str(BASE_DIR / "runtime" / "final_submission_v47_5"))).expanduser().resolve()
    proof_center_dir: Path = Path(_env("LMCP_PROOF_CENTER_DIR", str(BASE_DIR / "runtime" / "proof_center"))).expanduser().resolve()
    operator_auth_db_path: Path = Path(_env("LMCP_OPERATOR_AUTH_DB_PATH", str(BASE_DIR / "runtime" / "operator_auth" / "operator_auth.sqlite3"))).expanduser().resolve()
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

    def ensure_directories(self) -> None:
        for directory in (
            self.runtime_dir,
            self.monthly_quotes_dir,
            self.log_dir,
            self.handwriting_runtime_dir,
            self.tender_form_runtime_dir,
            self.clickable_navigation_runtime_dir,
            self.submission_proofs_dir,
            self.portal_submission_dir,
            self.final_submission_dir,
            self.proof_center_dir,
            self.operator_auth_db_path.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def configure_environment(self) -> None:
        os.environ.setdefault("LMCP_PROJECT_ROOT", str(self.project_root))
        os.environ.setdefault("LMCP_RUNTIME_DIR", str(self.runtime_dir))
        os.environ.setdefault("LMCP_ENV", self.environment)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config = Settings()
    config.configure_environment()
    try:
        config.ensure_directories()
    except (PermissionError, OSError):
        fallback_runtime = BASE_DIR / "runtime"
        object.__setattr__(config, "project_root", BASE_DIR)
        object.__setattr__(config, "runtime_dir", fallback_runtime)
        object.__setattr__(config, "monthly_quotes_dir", BASE_DIR / "monthly_quotes")
        object.__setattr__(config, "log_dir", fallback_runtime / "logs")
        object.__setattr__(config, "handwriting_runtime_dir", fallback_runtime / "handwriting_simulation")
        object.__setattr__(config, "tender_form_runtime_dir", fallback_runtime / "tender_form_intelligence")
        object.__setattr__(config, "clickable_navigation_runtime_dir", fallback_runtime / "clickable_navigation_v40")
        object.__setattr__(config, "submission_proofs_dir", fallback_runtime / "submission_proofs")
        object.__setattr__(config, "portal_submission_dir", fallback_runtime / "portal_submission")
        object.__setattr__(config, "final_submission_dir", fallback_runtime / "final_submission_v47_5")
        object.__setattr__(config, "proof_center_dir", fallback_runtime / "proof_center")
        object.__setattr__(config, "temp_dir", fallback_runtime / "tmp")
        object.__setattr__(config, "exports_dir", fallback_runtime / "exports")
        object.__setattr__(config, "audit_trail_dir", fallback_runtime / "audit_trail")
        object.__setattr__(config, "submission_history_dir", fallback_runtime / "submission_history")
        object.__setattr__(config, "health_dir", fallback_runtime / "health")
        object.__setattr__(config, "locks_dir", fallback_runtime / "locks")
        object.__setattr__(config, "operator_auth_db_path", fallback_runtime / "operator_auth" / "operator_auth.sqlite3")
        config.ensure_directories()
    return config


settings = get_settings()
