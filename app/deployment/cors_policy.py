from __future__ import annotations

import os
from typing import Tuple


def get_cors_origins() -> Tuple[str, ...]:
    raw = os.getenv("LMCP_CORS_ORIGINS", "*")
    return tuple(part.strip() for part in raw.split(",") if part.strip())
