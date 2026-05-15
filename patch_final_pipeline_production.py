#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "app/services/tender_pipeline.py"

IMPORTS = [
    "from app.services.pricing_engine_v2_realistic import apply_realistic_pricing_v2\n",
    "from app.services.auto_proof_after_submission_v2 import attach_auto_proof_to_result\n",
]

HELPERS = r