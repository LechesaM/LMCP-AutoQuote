from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from app.core.runtime_config import get_runtime_config


class PilotMode(str, Enum):
    DISABLED = "disabled"
    DRY_RUN = "dry_run"
    SUPERVISED_LIVE = "supervised_live"


def _raw_mode(environ: Mapping[str, str] | None = None) -> str:
    source = environ if environ is not None else os.environ
    return str(source.get("LMCP_PILOT_MODE", "") or "").strip().lower()


def get_pilot_mode(environ: Mapping[str, str] | None = None) -> PilotMode:
    raw = _raw_mode(environ)
    if raw == PilotMode.DRY_RUN.value:
        return PilotMode.DRY_RUN
    if raw == PilotMode.SUPERVISED_LIVE.value:
        return PilotMode.SUPERVISED_LIVE
    return PilotMode.DISABLED


def is_pilot_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return get_pilot_mode(environ) is not PilotMode.DISABLED


def get_pilot_execution_metadata(environ: Mapping[str, str] | None = None) -> Dict[str, Any]:
    config = get_runtime_config()
    mode = get_pilot_mode(environ)
    return {
        "pilot_mode": mode.value,
        "pilot_enabled": mode is not PilotMode.DISABLED,
        "dry_run": mode is PilotMode.DRY_RUN,
        "supervised_live": mode is PilotMode.SUPERVISED_LIVE,
        "manual_production_enforced": config.manual_production_enforced,
        "final_submission_manual_only": config.final_submission_manual_only,
        "operator_supervision_required": mode is PilotMode.SUPERVISED_LIVE,
    }


def is_supervised_live(environ: Mapping[str, str] | None = None) -> bool:
    return get_pilot_mode(environ) is PilotMode.SUPERVISED_LIVE
