#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "app/services/tender_pipeline.py"
IMPORT_LINE = "from app.services.pricing_engine_v2_realistic import apply_realistic_pricing_v2\n"

HOOK = '''
    # PRICING V2 REALISTIC MARGIN HOOK
    try:
        payload = apply_realistic_pricing_v2(payload)
        if not bool(payload.get("quote_ready", True)):
            payload.setdefault("pipeline_status", "manual_review_required")
            payload.setdefault("submission_status", "manual_review_required")
            return payload
    except Exception as pricing_v2_exc:
        payload["pricing_engine_v2_error"] = str(pricing_v2_exc)
'''


def backup(path: Path) -> None:
    dst = path.with_suffix(path.suffix + f".bak_pricing_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    dst.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Backup: {dst}")


def main() -> int:
    if not PIPELINE.exists():
        print("MISSING: app/services/tender_pipeline.py")
        return 1

    text = PIPELINE.read_text(encoding="utf-8")

    if "apply_realistic_pricing_v2(" in text:
        print("OK: tender_pipeline.py already contains Pricing V2 hook.")
        return 0

    backup(PIPELINE)

    if IMPORT_LINE.strip() not in text:
        lines = text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from app.services.") or line.startswith("import app.services."):
                insert_at = i
                break
            if line.startswith("import ") or line.startswith("from "):
                insert_at = i + 1
        lines.insert(insert_at, IMPORT_LINE)
        text = "".join(lines)

    markers = [
        "    # BEFORE_QUOTE_PACK_SERVICE",
        "    # BEFORE_QUOTE_ENGINE",
        "    # BEFORE_SUBMISSION",
        "    # BEFORE_EMAIL_SUBMISSION",
    ]

    inserted = False
    for marker in markers:
        if marker in text:
            text = text.replace(marker, HOOK + "\n" + marker, 1)
            inserted = True
            break

    if not inserted:
        # Fallback: insert before the first obvious quote pack call.
        for marker in ["quote_pack", "QuotePack", "build_quote", "submission_pack"]:
            idx = text.find(marker)
            if idx != -1:
                line_start = text.rfind("\n", 0, idx)
                text = text[: line_start + 1] + HOOK + text[line_start + 1 :]
                inserted = True
                break

    if not inserted:
        print("WARNING: Could not auto-insert hook. Add HOOK manually before quote generation/submission.")
        print(HOOK)
        PIPELINE.write_text(text, encoding="utf-8")
        return 2

    PIPELINE.write_text(text, encoding="utf-8")
    print("CHANGED: app/services/tender_pipeline.py")
    print("Pricing V2 hook inserted before quote/submission stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
