#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "app/services/tender_pipeline.py"

IMPORT_LINE = "from app.services.auto_proof_after_submission_v2 import attach_auto_proof_to_result\n"

HOOK = '''
        # AUTO PROOF AFTER SUBMISSION
        try:
            result = attach_auto_proof_to_result(result)
        except Exception as auto_proof_exc:
            result["auto_proof_result"] = {
                "status": "failed",
                "proof_generated": False,
                "error": str(auto_proof_exc),
            }
'''


def backup(path: Path) -> None:
    dst = path.with_suffix(path.suffix + f".bak_auto_proof_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    dst.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print("Backup:", dst)


def add_import(text: str) -> str:
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


def main() -> int:
    if not PIPELINE.exists():
        raise SystemExit("app/services/tender_pipeline.py not found")

    text = PIPELINE.read_text(encoding="utf-8")

    if "AUTO PROOF AFTER SUBMISSION" in text:
        print("OK: auto proof hook already installed")
        return 0

    backup(PIPELINE)
    text = add_import(text)

    markers = [
        'result["submission_status"] = "submitted"',
        'payload["submission_status"] = "submitted"',
        '"Email submission sent successfully."',
    ]

    inserted = False
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            line_end = text.find("\n", idx)
            if line_end == -1:
                line_end = idx
            text = text[: line_end + 1] + HOOK + text[line_end + 1 :]
            inserted = True
            break

    if not inserted:
        print("WARNING: Could not find exact submission-success marker.")
        print("Manual hook to add after successful submission:")
        print(HOOK)
        PIPELINE.write_text(text, encoding="utf-8")
        return 2

    PIPELINE.write_text(text, encoding="utf-8")
    compile(text, str(PIPELINE), "exec")
    print("OK: auto proof hook installed in tender_pipeline.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
