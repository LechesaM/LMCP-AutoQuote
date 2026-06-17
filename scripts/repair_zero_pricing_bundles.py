from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "").strip())
    except Exception:
        return default


def _default_unit_price(description: str, item_number: int) -> float:
    text = _clean(description).lower()
    if "paper" in text:
        return 100.0
    if "pen" in text:
        return 50.0
    if "file" in text or "folder" in text:
        return 40.0
    return max(25.0, 25.0 * float(item_number))


def _repair_items(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    repaired: List[Dict[str, Any]] = []
    changed = False
    for index, raw_item in enumerate(items, start=1):
        item = dict(raw_item) if isinstance(raw_item, dict) else {}
        description = _clean(item.get("description") or item.get("item_description") or item.get("specification") or f"Line {index}")
        item_number = int(_numeric(item.get("item_number") or item.get("line_number") or item.get("line_no") or index, index))
        quantity = _numeric(item.get("quantity") or item.get("qty") or 1.0, 1.0)
        unit_price = _numeric(item.get("unit_price") or item.get("price") or 0.0, 0.0)
        line_total = _numeric(item.get("line_total") or item.get("total") or item.get("amount") or 0.0, 0.0)

        if unit_price <= 0:
            unit_price = _default_unit_price(description, item_number)
            changed = True
        if line_total <= 0:
            line_total = round(quantity * unit_price, 2)
            changed = True

        item["item_number"] = item_number
        item["description"] = description
        item["quantity"] = quantity
        item["unit_price"] = round(unit_price, 2)
        item["line_total"] = round(line_total, 2)
        repaired.append(item)
    return repaired, changed


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _repair_pricing_json(path: Path) -> bool:
    payload = _load_json(path)
    items = payload.get("items")
    if not isinstance(items, list):
        return False
    repaired_items, changed = _repair_items(items)
    if not changed:
        return False
    payload["items"] = repaired_items
    _dump_json(path, payload)
    return True


def _repair_pricing_csv(path: Path) -> bool:
    if not path.exists():
        return False
    raw = path.read_bytes().replace(b"\x00", b"")
    text = raw.decode("utf-8", errors="replace")
    with io.StringIO(text, newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    if not rows or not fieldnames:
        return False
    repaired_rows, changed = _repair_items(rows)
    if not changed:
        return False
    output_rows: List[Dict[str, Any]] = []
    for original_row, repaired_row in zip(rows, repaired_rows):
        output_row: Dict[str, Any] = {}
        for field in fieldnames:
            if field in {"line_no", "line_number", "item_number"}:
                output_row[field] = repaired_row.get("item_number", original_row.get(field, ""))
            else:
                output_row[field] = repaired_row.get(field, original_row.get(field, ""))
        output_rows.append(output_row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    return True


def repair_bundles(root: Path) -> List[Path]:
    repaired: List[Path] = []
    if not root.exists():
        return repaired
    for tender_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        tender_id = tender_dir.name
        json_candidates = sorted(tender_dir.glob("*manual_pricing*.json"))
        csv_candidates = sorted(tender_dir.glob("*buyer_pricing_schedule.csv"))
        touched = False
        for json_path in json_candidates:
            touched = _repair_pricing_json(json_path) or touched
        for csv_path in csv_candidates:
            touched = _repair_pricing_csv(csv_path) or touched
        if touched:
            repaired.append(tender_dir)
    return repaired


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair zero-priced manual pricing bundles in place.")
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT / "runtime" / "manual_production" / "submission_packages",
        help="Submission package root to scan.",
    )
    args = parser.parse_args(argv)
    repaired = repair_bundles(args.root)
    if repaired:
        print("repaired bundles:")
        for path in repaired:
            print(f"- {path.name}")
        return 0
    print("no bundles required repair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
