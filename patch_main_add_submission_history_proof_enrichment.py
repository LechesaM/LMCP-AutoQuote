#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path

MAIN = Path("app/main.py")
IMPORT_LINE = "from app.api.submission_history_proof_enrichment_api import router as submission_history_proof_enrichment_router\n"
INCLUDE_LINE = '_safe_include_router("submission_history_proof_enrichment_router", submission_history_proof_enrichment_router)\n'


def main() -> None:
    if not MAIN.exists():
        raise SystemExit("app/main.py not found")

    text = MAIN.read_text(encoding="utf-8")
    backup = MAIN.with_suffix(MAIN.suffix + f".bak_proof_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup.write_text(text, encoding="utf-8")

    if "submission_history_proof_enrichment_api" not in text:
        lines = text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from app.api.") or line.startswith("import app.api."):
                insert_at = i + 1
        lines.insert(insert_at, IMPORT_LINE)
        text = "".join(lines)

    if "submission_history_proof_enrichment_router" not in text.replace(IMPORT_LINE, ""):
        marker = '_safe_include_router("proof_of_submission_router", proof_of_submission_router)\n'
        if marker in text:
            text = text.replace(marker, marker + INCLUDE_LINE)
        else:
            marker = '_safe_include_router("submission_history_pipeline_sync_router", submission_history_pipeline_sync_router)\n'
            text = text.replace(marker, marker + INCLUDE_LINE)

    # Add endpoint hints if not already present.
    if '"submission_history_recent_with_proofs_url"' not in text:
        text = text.replace(
            '"submission_proof_generate_all_url": "/submission-proof/generate-all",',
            '"submission_proof_generate_all_url": "/submission-proof/generate-all",\n'
            '        "submission_history_proof_sync_url": "/submission-history/proof-sync",\n'
            '        "submission_history_recent_with_proofs_url": "/submission-history/recent-with-proofs",'
        )

    MAIN.write_text(text, encoding="utf-8")
    print("OK: app/main.py patched")
    print("Backup:", backup)
    print("Added endpoints:")
    print("POST /submission-history/proof-sync")
    print("GET  /submission-history/recent-with-proofs")


if __name__ == "__main__":
    main()
