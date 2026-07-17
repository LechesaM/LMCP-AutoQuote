from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _resolve_project_root() -> Path:
    explicit = os.getenv("LMCP_PROJECT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()

    container_root = Path("/app")
    if (container_root / "app").is_dir():
        return container_root.resolve()

    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _resolve_project_root()
RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", str(PROJECT_ROOT / "runtime"))).expanduser().resolve()
LOG_DIR = Path(os.getenv("LMCP_LOG_DIR", str(RUNTIME_DIR / "logs"))).expanduser().resolve()
MONTHLY_QUOTES_DIR = Path(os.getenv("MONTHLY_QUOTES_ROOT", str(PROJECT_ROOT / "monthly_quotes"))).expanduser().resolve()


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def ensure_runtime_directories() -> None:
    ensure_directories([RUNTIME_DIR, LOG_DIR, MONTHLY_QUOTES_DIR])
