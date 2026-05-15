import json
from pathlib import Path

from app.services.tender_form_priority_engine import save_tender_submission_plan


TEST_TENDER_ROOT = "runtime/test_tender_pack"
TEST_OUTPUT = "runtime/test_outputs/tender_submission_plan.json"


def main():
    Path("runtime/test_tender_pack").mkdir(parents=True, exist_ok=True)
    Path("runtime/test_outputs").mkdir(parents=True, exist_ok=True)

    # Put your real tender pack files into runtime/test_tender_pack before running this.
    output = save_tender_submission_plan(
        output_path=TEST_OUTPUT,
        tender_root=TEST_TENDER_ROOT,
        tender_id="TEST-RFQ-001",
        instructions_text=(
            "Bidders must submit SBD 4, SBD 8, SBD 9 and pricing schedule. "
            "Complete all returnable documents contained in the tender document."
        ),
        mandatory_form_codes=["sbd4", "sbd8", "sbd9", "pricing_schedule"],
        enable_archive_extract=True,
    )

    print(f"Plan saved to: {output}")
    print(Path(output).read_text(encoding='utf-8'))


if __name__ == "__main__":
    main()
