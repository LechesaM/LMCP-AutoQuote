#!/usr/bin/env python3
"""
Adds the V48 submission history recent router to app/main.py.

Run from project root:
  cd /Users/Shared/LMCP-AutoQuote-Server
  python3 patch_main_add_submission_history_recent.py
"""

from pathlib import Path
from datetime import datetime
import sys

MAIN = Path("app/main.py")

IMPORT_LINE = "from app.api.submission_history_recent_api import router as submission_history_recent_router\n"
INCLUDE_LINE = 'app.include_router(submission_history_recent_router)\n'


def main():
    if not MAIN.exists():
        print(f"ERROR: {MAIN} not found")
        sys.exit(1)

    text = MAIN.read_text(encoding="utf-8")
    backup = MAIN.with_suffix(MAIN.suffix + f".bak_submission_history_recent_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup.write_text(text, encoding="utf-8")

    changed = False

    if "submission_history_recent_api" not in text:
        # Put import after last app.api import if possible, otherwise at top.
        lines = text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from app.api.") or line.startswith("import app.api."):
                insert_at = i + 1
        lines.insert(insert_at, IMPORT_LINE)
        text = "".join(lines)
        changed = True

    if "submission_history_recent_router" not in text.replace(IMPORT_LINE, ""):
        marker = "app = FastAPI"
        include_inserted = False

        lines = text.splitlines(keepends=True)
        # Prefer placing after other include_router calls.
        insert_at = None
        for i, line in enumerate(lines):
            if ".include_router(" in line:
                insert_at = i + 1

        if insert_at is not None:
            lines.insert(insert_at, INCLUDE_LINE)
            include_inserted = True
        else:
            # Last resort: append at bottom.
            lines.append("\n" + INCLUDE_LINE)
            include_inserted = True

        text = "".join(lines)
        changed = changed or include_inserted

    MAIN.write_text(text, encoding="utf-8")

    print("OK: patched app/main.py")
    print("Backup:", backup)
    print()
    print("Now run:")
    print("  python3 -m py_compile app/services/submission_history_recent_service.py app/api/submission_history_recent_api.py app/main.py")
    print("  docker compose restart api")
    print("  sleep 8")
    print("  curl http://localhost:8000/submission-history/recent")


if __name__ == "__main__":
    main()
