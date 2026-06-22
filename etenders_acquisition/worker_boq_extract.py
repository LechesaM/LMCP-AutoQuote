import subprocess
import sys
import time
from pathlib import Path


PIPELINE_STEPS = [
    {
        "name": "Document discovery",
        "command": ["python3", "document_discovery_worker.py"],
        "required": True,
    },
    {
        "name": "Document download batch 1",
        "command": ["python3", "document_downloader_worker.py"],
        "required": False,
    },
    {
        "name": "Document download batch 2",
        "command": ["python3", "document_downloader_worker.py"],
        "required": False,
    },
    {
        "name": "BOQ candidate detection",
        "command": ["python3", "boq_extraction_worker.py"],
        "required": True,
    },
    {
        "name": "BOQ candidate detection continuation",
        "command": ["python3", "boq_extraction_worker.py"],
        "required": False,
    },
    {
        "name": "Spreadsheet BOQ extraction",
        "command": ["python3", "spreadsheet_boq_extractor.py"],
        "required": False,
    },
    {
        "name": "PDF BOQ extraction batch 1",
        "command": ["python3", "pdf_boq_extractor.py"],
        "required": False,
    },
    {
        "name": "PDF BOQ extraction batch 2",
        "command": ["python3", "pdf_boq_extractor.py"],
        "required": False,
    },
    {
        "name": "PDF BOQ extraction batch 3",
        "command": ["python3", "pdf_boq_extractor.py"],
        "required": False,
    },
    {
        "name": "BOQ item normalization",
        "command": ["python3", "boq_item_normalizer.py"],
        "required": False,
    },
    {
        "name": "Priceable item classification",
        "command": ["python3", "priceable_item_classifier.py"],
        "required": True,
    },
    {
        "name": "Pricing engine",
        "command": ["python3", "pricing_engine.py"],
        "required": True,
    },
    {
        "name": "Pricing validation",
        "command": ["python3", "pricing_validator.py"],
        "required": True,
    },
    {
        "name": "Tender pricing summaries",
        "command": ["python3", "tender_pricing_summary.py"],
        "required": True,
    },
    {
        "name": "Attach pricing to quote packs",
        "command": ["python3", "attach_pricing_to_quote_packs.py"],
        "required": True,
    },
    {
        "name": "Quote pack index",
        "command": ["python3", "quote_pack_index.py"],
        "required": True,
    },
    {
        "name": "Dashboard quote-pack metrics",
        "command": ["python3", "quote_pack_dashboard_metrics.py"],
        "required": True,
    },
]


def run_step(step):
    print("\n" + "=" * 80)
    print(f"RUNNING: {step['name']}")
    print("=" * 80)

    started = time.time()

    result = subprocess.run(
        step["command"],
        cwd=Path(__file__).resolve().parent,
        text=True,
        capture_output=True,
    )

    elapsed = time.time() - started

    if result.stdout:
        print(result.stdout.strip())

    if result.stderr:
        print(result.stderr.strip())

    ok = result.returncode == 0

    print(
        f"STEP COMPLETE: {step['name']} | "
        f"status={'OK' if ok else 'FAILED'} | "
        f"elapsed={elapsed:.2f}s"
    )

    if not ok and step.get("required"):
        raise RuntimeError(
            f"Required step failed: {step['name']} "
            f"returncode={result.returncode}"
        )

    return ok


def main():
    print("Starting unified BOQ extraction and pricing pipeline...")

    started = time.time()
    passed = 0
    failed = 0

    for step in PIPELINE_STEPS:
        try:
            ok = run_step(step)
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\nPIPELINE STOPPED: {e}")
            sys.exit(1)

    elapsed = time.time() - started

    print("\n" + "=" * 80)
    print("UNIFIED BOQ PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Steps passed: {passed}")
    print(f"Steps failed/non-critical: {failed}")
    print(f"Elapsed: {elapsed:.2f}s")
    print("\nRefresh dashboard after completion.")


if __name__ == "__main__":
    main()
