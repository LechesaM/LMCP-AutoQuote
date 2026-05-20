from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.core.runtime_config import env, env_bool
from app.core.runtime_paths import get_runtime_paths


@dataclass(frozen=True)
class PostgresConfig:
    backend: str
    database_url: str
    host: str
    port: int
    database: str
    user: str
    password: str
    sslmode: str = "prefer"
    configured: bool = False
    production_warning: str = ""

    def to_jsonable_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "database_url": self.database_url,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "sslmode": self.sslmode,
            "configured": self.configured,
            "production_warning": self.production_warning,
        }


def parse_database_url(database_url: str) -> Dict[str, Any]:
    parsed = urlparse(str(database_url or "").strip())
    return {
        "scheme": parsed.scheme,
        "username": parsed.username or "",
        "password": parsed.password or "",
        "hostname": parsed.hostname or "",
        "port": int(parsed.port or 0),
        "database": parsed.path.lstrip("/"),
    }


def _fallback_postgres_config() -> PostgresConfig:
    backend = env("LMCP_DB_BACKEND", "sqlite").lower()
    database_url = env("LMCP_DATABASE_URL", "")
    if database_url:
        parts = parse_database_url(database_url)
        return PostgresConfig(
            backend=backend,
            database_url=database_url,
            host=parts["hostname"],
            port=parts["port"] or 5432,
            database=parts["database"],
            user=parts["username"],
            password=parts["password"],
            configured=backend == "postgres" and bool(parts["hostname"] and parts["database"] and parts["username"]),
            production_warning="",
        )
    host = env("LMCP_POSTGRES_HOST", "localhost")
    port = int(env("LMCP_POSTGRES_PORT", "5432"))
    database = env("LMCP_POSTGRES_DB", "lmcp")
    user = env("LMCP_POSTGRES_USER", "lmcp")
    password = env("LMCP_POSTGRES_PASSWORD", "")
    database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    return PostgresConfig(
        backend=backend,
        database_url=database_url,
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        configured=backend == "postgres" and bool(host and database and user),
        production_warning="",
    )


def get_postgres_config() -> PostgresConfig:
    config = _fallback_postgres_config()
    profile_name = env("LMCP_DEPLOYMENT_PROFILE", "local_dev").lower()
    warning = ""
    if profile_name in {"production", "supervised_live"} and config.backend == "sqlite":
        warning = "SQLite is configured in a supervised-live or production profile; PostgreSQL is recommended."
    return PostgresConfig(
        backend=config.backend,
        database_url=config.database_url,
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
        sslmode=config.sslmode,
        configured=config.configured,
        production_warning=warning,
    )


def postgres_connection_ready() -> bool:
    config = get_postgres_config()
    return config.backend == "postgres" and bool(config.database_url and config.configured)


def supervised_live_db_fallback_allowed() -> bool:
    profile_name = env("LMCP_DEPLOYMENT_PROFILE", "local_dev").lower()
    return profile_name == "supervised_live" and not postgres_connection_ready()


def postgres_readiness_report() -> Dict[str, Any]:
    config = get_postgres_config()
    report = config.to_jsonable_dict()
    report["connection_ready"] = postgres_connection_ready()
    report["fallback_allowed"] = supervised_live_db_fallback_allowed()
    report["runtime_db_path"] = str(get_runtime_paths().manual_production_db_path)
    report["backend"] = config.backend
    return report
