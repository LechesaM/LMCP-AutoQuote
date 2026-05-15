#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PIPELINE = ROOT / "app/services/tender_pipeline.py"
FULL_CYCLE = ROOT / "app/services/full_autonomous_cycle_service.py"

IMPORT_LINE = "from app.services.pricing_engine_v2_realistic import apply_realistic_pricing_v2\n"

HOOK = """
        # PRICING V2 REALISTIC MARGIN GUARD
        try:
            pipeline_payload = apply_realistic_pricing_v2(pipeline_payload)
            item["pipeline_payload"] = pipeline_payload

            pricing_summary = pipeline_payload.get("pricing_summary", {})
            item["pricing_v2_summary"] = pricing_summary

            if not bool(pipeline_payload.get("quote_ready", True)):
                item["status"] = "manual_review_pricing_v2"
                item["pricing_engine_status"] = pipeline_payload.get("pricing_engine_status")
                item["pricing_summary"] = pricing_summary
                cycle["blocked"] += 1
                cycle["items"].append(item)
                continue
        except Exception as pricing_v2_exc:
            item["pricing_v2_error"] = str(pricing_v2_exc)
"""


def _latest_backup() -> Path | None:
    backups = sorted(
        list(PIPELINE.parent.glob("tender_pipeline.py.bak_pricing_v2_*"))
        + list(PIPELINE.parent.glob("tender_pipeline.py.broken_indent_*")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # Prefer the original clean backup, not the broken file.
    clean_backups = [p for p in backups if ".bak_pricing_v2_" in p.name]
    return clean_backups[0] if clean_backups else (backups[0] if backups else None)


def restore_tender_pipeline() -> None:
    backup = _latest_backup()
    if not backup:
        raise SystemExit("No tender_pipeline backup found. Cannot safely restore.")

    current_backup = PIPELINE.with_suffix(
        PIPELINE.suffix + f".broken_before_safe_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    if PIPELINE.exists():
        current_backup.write_text(PIPELINE.read_text(encoding="utf-8"), encoding="utf-8")
        print("Saved current broken tender_pipeline:", current_backup)

    PIPELINE.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
    print("Restored tender_pipeline.py from:", backup)

    # Validate restored pipeline before touching anything else.
    compile(PIPELINE.read_text(encoding="utf-8"), str(PIPELINE), "exec")
    print("Syntax OK: restored tender_pipeline.py")


def add_import_to_full_cycle(text: str) -> str:
    if IMPORT_LINE.strip() in text:
        return text

    lines = text.splitlines(keepends=True)
    insert_at = 0

    for i, line in enumerate(lines):
        if line.startswith("from app.services.") or line.startswith("import app.services."):
            insert_at = i
            break
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1

    lines.insert(insert_at, IMPORT_LINE)
    return "".join(lines)


def patch_full_cycle() -> None:
    if not FULL_CYCLE.exists():
        raise SystemExit("app/services/full_autonomous_cycle_service.py not found.")

    text = FULL_CYCLE.read_text(encoding="utf-8")

    if "PRICING V2 REALISTIC MARGIN GUARD" in text:
        print("OK: full_autonomous_cycle_service.py already has Pricing V2 guard.")
        compile(text, str(FULL_CYCLE), "exec")
        return

    backup = FULL_CYCLE.with_suffix(
        FULL_CYCLE.suffix + f".bak_safe_pricing_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    backup.write_text(text, encoding="utf-8")
    print("Backup full_autonomous_cycle_service:", backup)

    text = add_import_to_full_cycle(text)

    markers = [
        '        item["pipeline_payload"] = pipeline_payload\n',
        '        item["pipeline_payload"] = dict(pipeline_payload)\n',
    ]

    patched = False
    for marker in markers:
        if marker in text:
            text = text.replace(marker, marker + HOOK + "\n", 1)
            patched = True
            break

    if not patched:
        # Safer fallback: before force_quote call.
        marker = "force_quote("
        idx = text.find(marker)
        if idx == -1:
            raise SystemExit("Could not find safe insertion point in full_autonomous_cycle_service.py.")
        line_start = text.rfind("\n", 0, idx)
        text = text[: line_start + 1] + HOOK + "\n" + text[line_start + 1 :]

    FULL_CYCLE.write_text(text, encoding="utf-8")
    compile(FULL_CYCLE.read_text(encoding="utf-8"), str(FULL_CYCLE), "exec")
    print("Syntax OK: full_autonomous_cycle_service.py")
    print("Pricing V2 guard safely added before force_quote/pipeline call.")


def main() -> int:
    print("LMCP Restore Pipeline + Apply Pricing V2 Safely")
    print("=" * 55)

    restore_tender_pipeline()
    patch_full_cycle()

    print("\nNext commands:")
    print("python3 -m py_compile app/services/pricing_engine_v2_realistic.py app/services/tender_pipeline.py app/services/full_autonomous_cycle_service.py app/main.py")
    print("docker compose restart api")
    print("sleep 8")
    print("curl http://localhost:8000/health")
    print("curl -X POST http://localhost:8000/full-autonomous-cycle/run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
