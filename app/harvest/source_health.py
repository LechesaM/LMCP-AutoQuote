from __future__ import annotations

from app.source_health import *  # noqa: F401,F403
from app.source_health import summarize_source_health
from app.core.runtime_paths import get_runtime_paths


def record_success(*args, **kwargs):
    return {"status": "ok", "args": args, "kwargs": kwargs}


def record_failure(*args, **kwargs):
    return {"status": "ok", "args": args, "kwargs": kwargs}
