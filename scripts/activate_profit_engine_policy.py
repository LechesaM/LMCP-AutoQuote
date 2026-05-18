#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
PROFIT_DIR = RUNTIME / "profit_engine"
PROFIT_DIR.mkdir(parents=True, exist_ok=True)

policy = {
    "status": "active",
    "engine": "LMCP_PROFIT_ENGINE_PRODUCTION_POLICY",
    "activated_at": datetime.now(timezone.utc).isoformat(),
    "minimum_profit_required": 30000.0,
    "minimum_margin_percent": 25.0,
    "single_line_max_margin_percent": 45.0,
    "multi_line_max_margin_percent": 55.0,
    "single_line_max_markup_percent": 80.0,
    "multi_line_max_markup_percent": 120.0,
    "reject_if_profit_below_required": True,
    "reject_if_margin_below_required": True,
    "manual_review_if_pricing_unrealistic": True,
    "blocked_categories": [
        "medical consumables",
        "IT equipment",
        "petrol",
        "diesel",
        "catering",
        "briefing session required"
    ],
    "preferred_submission_methods": ["email", "portal"],
    "notes": [
        "Pricing V2 remains final pricing authority.",
        "Legacy pricing must not control final quote output.",
        "Portal/email submissions remain subject to go-live guards and confidence checks."
    ]
}

(PROFIT_DIR / "profit_policy.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")
print("OK: Profit Engine production policy written")
print(json.dumps(policy, indent=2))
