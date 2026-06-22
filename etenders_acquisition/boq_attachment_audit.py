#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
QUOTE_PACKS_DIR = RUNTIME_DIR / "manual_production"

BOQ_HINTS = [
    "boq",
    "bill",
    "schedule",
    "pricing",
    "price",
    "rates",
    "quantities",
    "bills",
    "costing",
]

VALID_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".xls",
    ".csv",
    ".docx",
}


def detect_boq_files(folder):
    detected = []

    for path in folder.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in VALID_EXTENSIONS:
            continue

        name = path.name.lower()

        if any(hint in name for hint in BOQ_HINTS):
            detected.append(path)

    return detected


def main():
    pack_dirs = [p for p in QUOTE_PACKS_DIR.iterdir() if p.is_dir()]

    stats = Counter()

    no_boq = []
    with_boq = []

    for pack in pack_dirs:
        boq_files = detect_boq_files(pack)

        if boq_files:
            stats["with_boq"] += 1

            with_boq.append({
                "pack": pack.name,
                "boq_files": [str(x) for x in boq_files]
            })

        else:
            stats["without_boq"] += 1

            no_boq.append(pack.name)

    output = {
        "summary": dict(stats),
        "without_boq": no_boq,
        "with_boq": with_boq,
    }

    out_file = RUNTIME_DIR / "boq_attachment_audit.json"

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"BOQ attachment audit written: {out_file}")
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
