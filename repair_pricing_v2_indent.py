#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "app/services/tender_pipeline.py"
SERVICE = ROOT / "app/services/pricing_engine_v2_realistic.py"
IMPORT_LINE = "from app.services.pricing_engine_v2_realistic import apply_realistic_pricing_v2\n"

HOOK = """
    # PRICING V2 REALISTIC MARGIN HOOK
    try:
        payload = apply_realistic_pricing_v2(payload)
        if not bool(payload.get("quote_ready", True)):
            payload.setdefault("pipeline_status", "manual_review_required")
            payload.setdefault("submission_status", "manual_review_required")
            return payload
    except Exception as pricing_v2_exc:
        payload["pricing_engine_v2_error"] = str(pricing_v2_exc)
"""


def latest_backup():
    backups = sorted(
        PIPELINE.parent.glob("tender_pipeline.py.bak_pricing_v2_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return backups[0] if backups else None


def restore_backup():
    backup = latest_backup()
    if not backup:
        raise SystemExit("No pricing_v2 backup found. Cannot safely restore tender_pipeline.py.")

    broken_backup = PIPELINE.with_suffix(
        PIPELINE.suffix + f".broken_indent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    if PIPELINE.exists():
        broken_backup.write_text(PIPELINE.read_text(encoding="utf-8"), encoding="utf-8")
        print("Saved broken file backup:", broken_backup)

    PIPELINE.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
    print("Restored:", backup)


def add_import(text):
    if IMPORT_LINE.strip() in text:
        return text

    lines = text.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1
            continue
        break

    lines.insert(insert_at, IMPORT_LINE)
    return "".join(lines)


def find_payload_function_insert(text):
    candidate_function_names = [
        "run_tender_pipeline_from_payload",
        "process_single_rfq",
        "run_pipeline",
        "process_rfq",
        "execute_pipeline",
    ]

    lines = text.splitlines(keepends=True)
    for fn in candidate_function_names:
        for i, line in enumerate(lines):
            if line.startswith(f"def {fn}") or line.startswith(f"async def {fn}"):
                for j in range(i + 1, min(i + 260, len(lines))):
                    current = lines[j]
                    if j > i + 1 and (current.startswith("def ") or current.startswith("async def ") or current.startswith("class ")):
                        break
                    if "BEFORE_QUOTE" in current or "quote_pack" in current or "QuotePack" in current or "submission_pack" in current:
                        return j, fn
                return i + 1, fn
    return None


def apply_hook():
    text = PIPELINE.read_text(encoding="utf-8")

    if "apply_realistic_pricing_v2(payload)" in text:
        print("Pricing V2 hook already exists after restore; skipping hook insert.")
        return

    text = add_import(text)
    found = find_payload_function_insert(text)
    if not found:
        raise SystemExit("Could not find a safe function insertion point. Restore completed; hook not added.")

    insert_index, fn_name = found
    lines = text.splitlines(keepends=True)
    lines.insert(insert_index, HOOK)
    PIPELINE.write_text("".join(lines), encoding="utf-8")
    print(f"Inserted Pricing V2 hook inside: {fn_name}")


def validate():
    compile(PIPELINE.read_text(encoding="utf-8"), str(PIPELINE), "exec")
    if SERVICE.exists():
        compile(SERVICE.read_text(encoding="utf-8"), str(SERVICE), "exec")
    print("Syntax OK: tender_pipeline.py")
    print("Syntax OK: pricing_engine_v2_realistic.py")


def main():
    print("LMCP Pricing V2 indent repair")
    print("=" * 40)
    restore_backup()
    apply_hook()
    validate()
    print("\nNext commands:")
    print("python3 -m py_compile app/services/pricing_engine_v2_realistic.py app/services/tender_pipeline.py app/main.py")
    print("docker compose restart api")
    print("sleep 8")
    print("curl http://localhost:8000/health")
    print("curl -X POST http://localhost:8000/full-autonomous-cycle/run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
