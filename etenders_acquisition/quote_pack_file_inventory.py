#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
QUOTE_PACK_INDEX_FILE = RUNTIME_DIR / "manual_production" / "quote_pack_index.json"
OUTPUT_FILE = RUNTIME_DIR / "manual_production" / "quote_pack_file_inventory.json"

DOC_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".txt", ".zip"
}

BOQ_HINTS = [
    "boq", "bill", "bills", "quantity", "quantities",
    "pricing", "price", "rates", "schedule", "returnable",
    "form of offer", "activity schedule", "scope"
]


def load_json(path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def file_kind(path):
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls", ".csv"}:
        return "spreadsheet"

    if suffix == ".pdf":
        return "pdf"

    if suffix in {".docx", ".doc"}:
        return "word"

    if suffix == ".zip":
        return "zip"

    if suffix == ".txt":
        return "text"

    return "other"


def has_boq_hint(path):
    name = path.name.lower()
    return any(hint in name for hint in BOQ_HINTS)


def main():
    index = load_json(QUOTE_PACK_INDEX_FILE, default={})
    packs = index.get("packs", [])

    inventory = []
    ext_counts = Counter()
    kind_counts = Counter()
    pack_status_counts = Counter()

    for pack in packs:
        tender_id = pack.get("tender_id", "UNKNOWN")
        pack_dir = Path(pack.get("pack_dir", ""))

        record = {
            "tender_id": tender_id,
            "pack_dir": str(pack_dir),
            "exists": pack_dir.exists(),
            "has_pricing": bool(pack.get("has_pricing")),
            "pricing_status": pack.get("pricing_status"),
            "files": [],
            "document_count": 0,
            "boq_candidate_count": 0,
        }

        if not pack_dir.exists():
            pack_status_counts["pack_dir_missing"] += 1
            inventory.append(record)
            continue

        files = [p for p in pack_dir.rglob("*") if p.is_file()]

        for f in files:
            suffix = f.suffix.lower()
            ext_counts[suffix or "[no_ext]"] += 1

            kind = file_kind(f)
            kind_counts[kind] += 1

            is_doc = suffix in DOC_EXTENSIONS
            is_boq_candidate = is_doc and has_boq_hint(f)

            if is_doc:
                record["document_count"] += 1

            if is_boq_candidate:
                record["boq_candidate_count"] += 1

            record["files"].append({
                "name": f.name,
                "path": str(f),
                "extension": suffix,
                "kind": kind,
                "size_bytes": f.stat().st_size,
                "is_document": is_doc,
                "is_boq_candidate": is_boq_candidate,
            })

        if record["boq_candidate_count"] > 0:
            pack_status_counts["has_boq_candidate"] += 1
        elif record["document_count"] > 0:
            pack_status_counts["has_docs_no_boq_candidate"] += 1
        else:
            pack_status_counts["no_documents"] += 1

        inventory.append(record)

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_index_packs": len(packs),
        "pack_status_counts": dict(pack_status_counts),
        "extension_counts": dict(ext_counts),
        "kind_counts": dict(kind_counts),
        "inventory": inventory,
    }

    write_json(OUTPUT_FILE, output)

    print(f"Inventory written: {OUTPUT_FILE}")
    print(f"Total index packs: {len(packs)}")
    print("Pack status counts:")
    for k, v in dict(pack_status_counts).items():
        print(f"- {k}: {v}")

    print("Kind counts:")
    for k, v in dict(kind_counts).items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
