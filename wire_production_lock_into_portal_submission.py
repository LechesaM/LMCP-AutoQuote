from __future__ import annotations

from pathlib import Path
from datetime import datetime

TARGET = Path("app/services/portal_submission_service.py")

IMPORT_LINE = "from app.services.production_lock_service import assert_production_submission_allowed\n"

GATE_BLOCK = """
    # ============================================================
    # LMCP PRODUCTION LOCK GATE
    # Blocks TEST/DEMO, expired tenders, briefing-session tenders,
    # excluded categories, low-profit and weak-margin submissions
    # before any portal upload/final-submit automation runs.
    # ============================================================
    try:
        production_decision = assert_production_submission_allowed(payload)
    except Exception as exc:
        production_decision = {
            "status": "blocked",
            "allowed": False,
            "submitted": False,
            "portal_auto_submitted": False,
            "submission_status": "blocked_by_production_lock_error",
            "message": "Production lock failed closed before portal submission.",
            "error": str(exc),
        }

    if not production_decision.get("allowed"):
        production_decision.update({
            "stage": "portal_auto_submission",
            "engine": "production_lock",
            "buyer_rfq_number": payload.get("buyer_rfq_number") or payload.get("rfq_number") or payload.get("reference_number"),
            "quote_number": payload.get("quote_number") or payload.get("lmcp_quote_number"),
            "portal_url": payload.get("portal_url") or payload.get("submission_url"),
        })
        return production_decision

"""


def find_function_body_insert_point(text: str, function_names: list[str]) -> tuple[int, str]:
    lines = text.splitlines(keepends=True)

    for fn in function_names:
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"async def {fn}(") or stripped.startswith(f"def {fn}("):
                # Insert immediately after function definition line.
                return sum(len(x) for x in lines[: i + 1]), fn

    raise RuntimeError(
        "Could not find an auto-submit function. Expected one of: "
        + ", ".join(function_names)
    )


def main() -> None:
    if not TARGET.exists():
        raise FileNotFoundError(f"Missing target file: {TARGET}")

    text = TARGET.read_text(encoding="utf-8")

    if "assert_production_submission_allowed" in text and "LMCP PRODUCTION LOCK GATE" in text:
        print("Production Lock gate already appears to be installed.")
        return

    backup = TARGET.with_suffix(
        TARGET.suffix + f".backup_before_production_lock_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    backup.write_text(text, encoding="utf-8")
    print(f"Backup created: {backup}")

    if "assert_production_submission_allowed" not in text:
        lines = text.splitlines(keepends=True)
        insert_import_at = 0

        for idx, line in enumerate(lines):
            if line.startswith("from __future__"):
                insert_import_at = idx + 1

        if insert_import_at == 0:
            for idx, line in enumerate(lines):
                if line.startswith(("import ", "from ")):
                    insert_import_at = idx + 1

        lines.insert(insert_import_at, IMPORT_LINE)
        text = "".join(lines)

    function_names = [
        "auto_submit_portal_submission",
        "portal_submission_auto_submit",
        "auto_submit",
        "submit_portal",
        "prepare_and_auto_submit",
        "prepare_portal_submission",
    ]

    insert_at, used_fn = find_function_body_insert_point(text, function_names)
    text = text[:insert_at] + GATE_BLOCK + text[insert_at:]

    TARGET.write_text(text, encoding="utf-8")
    print(f"Production Lock gate inserted into function: {used_fn}")
    print("Done.")


if __name__ == "__main__":
    main()
