#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
POLICY_DIR = RUNTIME / "full_autonomous_v48"
POLICY_DIR.mkdir(parents=True, exist_ok=True)

policy = {
    "enabled": True,
    "mode": "full_autonomous",
    "allow_email_send": True,
    "allow_portal_upload": True,
    "allow_portal_final_submit": True,
    "require_confirmation_phrase": False,
    "confirmation_phrase": "I CONFIRM FINAL SUBMISSION",
    "minimum_profit_required": 30000.0,
    "margin_percent": 25.0,
    "apply_profit_floor": True,
    "min_confidence": 0.35,
    "zip_allowed_for_submission": False,
    "captcha_bypass_allowed": False,
    "activated_at": datetime.now(timezone.utc).isoformat(),
}

(POLICY_DIR / "policy.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")

portal_state = {
    "status": "portal_automation_ready",
    "activated_at": datetime.now(timezone.utc).isoformat(),
    "required_routes": [
        "/portal-submission/status",
        "/etenders-session/status",
        "/smart-upload-v47-4/status",
        "/final-submission-v47-5/status",
        "/deep-verification-v47-7/status",
        "/full-autonomous-cycle/run",
    ],
    "next_manual_check": "Confirm browser session/profile is authenticated before unattended portal final submit.",
}

(RUNTIME / "portal_automation_activation.json").write_text(json.dumps(portal_state, indent=2), encoding="utf-8")

print("OK: Portal automation policy activated")
print(json.dumps(policy, indent=2))
