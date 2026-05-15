#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

POLICY_FILE = Path("runtime/full_autonomous_v48/policy.json")
POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)

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
}

POLICY_FILE.write_text(json.dumps(policy, indent=2), encoding="utf-8")

print("OK: V48 full autonomous policy written")
print(POLICY_FILE)
print(json.dumps(policy, indent=2))
