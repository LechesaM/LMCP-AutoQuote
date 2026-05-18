from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "generated_submission_packs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_submission_pack(opportunity_id: int | None = None) -> dict[str, Any]:
    timestamp = datetime.utcnow().isoformat()

    filename = f"submission_pack_{opportunity_id or 'general'}.txt"
    output_file = OUTPUT_DIR / filename

    content = []
    content.append("LMCP SUBMISSION PACK")
    content.append("====================")
    content.append(f"Opportunity ID: {opportunity_id}")
    content.append(f"Generated At: {timestamp}")
    content.append("")
    content.append("Status: Placeholder submission pack created successfully.")
    content.append("Next step: connect this builder to real quote, SBD, and compliance documents.")

    output_file.write_text("\n".join(content), encoding="utf-8")

    return {
        "status": "ok",
        "job": "build_submission_pack",
        "opportunity_id": opportunity_id,
        "file_path": str(output_file),
        "generated_at": timestamp,
    }


def auto_build_submission_packs() -> dict[str, Any]:
    timestamp = datetime.utcnow().isoformat()

    result = build_submission_pack()

    return {
        "job": "auto_build_submission_packs",
        "status": "ok",
        "timestamp": timestamp,
        "detail": "Submission pack cycle completed successfully.",
        "result": result,
    }
