from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_fixture_backed_fresh_intake import _write_harvest_source_boq_text, _write_harvest_source_summary_pdf


DEFAULT_SUBMISSION_PACKAGES_ROOT = PROJECT_ROOT / "runtime" / "manual_production" / "submission_packages"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except Exception:
        return []


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _build_candidate(bundle_dir: Path) -> Dict[str, Any]:
    quote_pack = _read_json(bundle_dir / f"{bundle_dir.name}__quote_pack.json")
    submission_manifest = _read_json(bundle_dir / f"{bundle_dir.name}__submission_package_manifest.json")
    buyer_schedule = _read_csv_rows(bundle_dir / f"{bundle_dir.name}__buyer_pricing_schedule.csv")
    title = _first_text(
        quote_pack.get("title"),
        submission_manifest.get("title"),
        bundle_dir.name,
    )
    buyer_name = _first_text(
        quote_pack.get("buyer_name"),
        submission_manifest.get("buyer_name"),
    )
    first_row = buyer_schedule[0] if buyer_schedule else {}
    description = _first_text(
        first_row.get("description"),
        first_row.get("item_description"),
        title,
    )
    line_items = buyer_schedule or [
        {
            "description": description,
            "quantity": 1,
            "unit_price": 150000.0,
            "line_total": 150000.0,
        }
    ]
    return {
        "title": title,
        "buyer_name": buyer_name,
        "description": description,
        "line_items": line_items,
    }


def repair_refresh_bundle_source_artifacts(submission_packages_root: Path) -> Dict[str, Any]:
    repaired_bundles: List[str] = []
    skipped_bundles: List[str] = []

    for bundle_dir in sorted(path for path in submission_packages_root.iterdir() if path.is_dir()):
        nested_source_dir = bundle_dir / "source_quotes"
        nested_source_pdf = nested_source_dir / f"{bundle_dir.name}__source_rfq.pdf"
        nested_source_boq = nested_source_dir / f"{bundle_dir.name}__source_rfq_boq.txt"
        if not nested_source_dir.exists() and not nested_source_pdf.exists() and not nested_source_boq.exists():
            skipped_bundles.append(bundle_dir.name)
            continue

        candidate = _build_candidate(bundle_dir)
        root_source_pdf = bundle_dir / f"{bundle_dir.name}__source_rfq.pdf"
        root_source_boq = bundle_dir / f"{bundle_dir.name}__source_rfq_boq.txt"

        if nested_source_pdf.exists():
            shutil.copy2(nested_source_pdf, root_source_pdf)
        else:
            _write_harvest_source_summary_pdf(root_source_pdf, candidate)

        if nested_source_boq.exists():
            shutil.copy2(nested_source_boq, root_source_boq)
        else:
            _write_harvest_source_boq_text(root_source_boq, candidate)

        manifest_path = bundle_dir / f"{bundle_dir.name}__submission_package_manifest.json"
        manifest = _read_json(manifest_path)
        source_entries = []
        for entry in manifest.get("source_quote_entries", []):
            text = str(entry or "").strip()
            if text:
                source_entries.append(text)
        for value in (str(root_source_pdf), str(root_source_boq), str(nested_source_pdf), str(nested_source_boq)):
            if value and value not in source_entries:
                source_entries.append(value)
        if source_entries:
            manifest["source_quote_entries"] = source_entries
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        repaired_bundles.append(bundle_dir.name)

    return {
        "submission_packages_root": str(submission_packages_root),
        "repaired_bundles": repaired_bundles,
        "repaired_count": len(repaired_bundles),
        "skipped_count": len(skipped_bundles),
        "skipped_bundles": skipped_bundles,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair refresh bundles with root-level source quote artifacts.")
    parser.add_argument("--submission-packages-root", type=Path, default=DEFAULT_SUBMISSION_PACKAGES_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = repair_refresh_bundle_source_artifacts(args.submission_packages_root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"submission packages root: {report['submission_packages_root']}")
        print(f"repaired count: {report['repaired_count']}")
        print(f"skipped count: {report['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
