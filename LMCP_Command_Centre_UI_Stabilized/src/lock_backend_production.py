#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

POLICY_DIR = ROOT / "runtime/full_autonomous_v48"
POLICY_DIR.mkdir(parents=True, exist_ok=True)

POLICY_FILE = POLICY_DIR / "policy.json"
BACKEND_LOCK_FILE = ROOT / "runtime/backend_lock.json"

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

lock = {
    "status": "locked",
    "locked_at": datetime.now(timezone.utc).isoformat(),
    "backend_phase": "production_frontend_wiring",
    "do_not_patch_pipeline": True,
    "reason": "Pipeline is stable: Pricing V2 active, submission works, proof_pdf_path exposed.",
    "required_markers": {
        "pricing_engine_override": "PRICING_V2_REALISTIC_POST_PRICING_OVERRIDE",
        "pricing_v2_active": True,
        "use_legacy_pricing": False,
        "auto_proof_after_submission": True,
    },
    "policy_file": str(POLICY_FILE),
}

POLICY_FILE.write_text(json.dumps(policy, indent=2), encoding="utf-8")
BACKEND_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
BACKEND_LOCK_FILE.write_text(json.dumps(lock, indent=2), encoding="utf-8")

print("OK: Backend locked for production frontend wiring")
print("Policy:", POLICY_FILE)
print("Lock:", BACKEND_LOCK_FILE)
print(json.dumps(lock, indent=2))
