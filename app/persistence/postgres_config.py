from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresConfig:
    backend: str
    host: str = "localhost"
    port: int = 5432
    database: str = "lmcp"
    configured: bool = False
    production_warning: str = ""


def get_postgres_config() -> PostgresConfig:
    backend = os.getenv("LMCP_DB_BACKEND", "sqlite").lower()
    if backend == "postgres":
        return PostgresConfig(backend="postgres", host="localhost", port=5432, database="lmcp", configured=True)
    return PostgresConfig(backend="sqlite", production_warning="PostgreSQL recommended for production")


def postgres_connection_ready() -> bool:
    return get_postgres_config().backend == "postgres"
