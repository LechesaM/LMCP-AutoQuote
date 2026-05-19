from __future__ import annotations

from typing import Tuple

from app.core.runtime_config import env_csv


def get_cors_origins(default: str = "*") -> Tuple[str, ...]:
    return env_csv("LMCP_CORS_ORIGINS", default)

