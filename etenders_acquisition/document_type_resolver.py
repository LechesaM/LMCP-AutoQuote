#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

DOC_ROOT = RUNTIME_DIR / "support_document_resolution" / "documents"
OUT_DIR = RUNTIME_DIR / "boq_intelligence"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUT_DIR / "document_type_inventory.json"

BOQ_HINTS = [
    "boq", "bill of quantities", "bill_of_quantities", "pricing schedule",
    "price schedule", "pricing data", "schedule of rates", "sor",
    "rate schedule", "form c", "annexure b_c", "quantities",
    "unpriced boq", "priced boq", "bill", "quotation schedule"
]

SPEC_HINTS = [
    "scope", "specification", "technical", "terms of reference",
    "tor", "works information", "goods information", "sow"
]

RETURNABLE_HINTS = [
    "returnable", "sbd", "declaration", "integrity", "tax",
    "local content", "preference", "bbbee", "bid conditions",
    "general conditions", "gcc", "form a", "form b"
]

CONTRACT_HINTS = [
    "nec", "contract", "agreement", "sla", "conditions of contract"
]

ADVERT_HINTS = [
    "advert", "notice", "invitation", "tear sheet", "publication"
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean(value):
    value = str(value or "").lower()
    value = re.sub(r"[_\-.]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def contains_any(text, hints):
    return [h for h in hints if h in text]


def classify_file(path):
    name = path.name
    lower_name = clean(name)
    ext = path.suffix.lower()

    boq_matches = contains_any(lower_name, BOQ_HINTS)
    spec_matches = contains_any(lower_name, SPEC_HINTS)
    returnable_matches = contains_any(lower_name, RETURNABLE_HINTS)
    contract_matches = contains_any(lower_name, CONTRACT_HINTS)
    advert_matches = contains_any(lower_name, ADVERT_HINTS)

    score = {
        "boq_or_pricing": len(boq_matches) * 20,
        "specification": len(spec_matches) * 12,
        "returnable": len(returnable_matches) * 10,
        "contract": len(contract_matches) * 8,
        "advert": len(advert_matches) * 6,
    }

    if ext in [".xlsx", ".xls", ".csv"]:
        score["boq_or_pricing"] += 20

    if ext in [".doc", ".docx"] and boq_matches:
        score["boq_or_pricing"] += 10

    if "pricing" in lower_name:
        score["boq_or_pricing"] += 25

    if "boq" in lower_name:
        score["boq_or_pricing"] += 35

    if "advert" in lower_name:
        score["advert"] += 25

    best_type = max(score, key=score.get)
    best_score = score[best_type]

    if best_score <= 0:
        best_type = "unclassified"

    is_price_candidate = best_type == "boq_or_pricing"

    return {
        "path": str(path),
        "filename": name,
        "extension": ext,
        "size_bytes": path.stat().st_size,
        "tender_folder": path.parent.name,
        "document_type": best_type,
        "document_score": best_score,
        "is_price_candidate": is_price_candidate,
        "matches": {
            "boq_or_pricing": boq_matches,
            "specification": spec_matches,
            "returnable": returnable_matches,
            "contract": contract_matches,
            "advert": advert_matches,
        },
        "scores": score,
    }


def main():
    files = []

    for path in DOC_ROOT.rglob("*"):
        if path.is_file() and path.name != "tender_metadata.json":
            files.append(path)

    inventory = []

    for path in sorted(files):
        try:
            inventory.append(classify_file(path))
        except Exception as e:
            inventory.append({
                "path": str(path),
                "filename": path.name,
                "extension": path.suffix.lower(),
                "tender_folder": path.parent.name,
                "document_type": "error",
                "error": str(e),
            })

    type_counts = Counter(item.get("document_type") for item in inventory)
    ext_counts = Counter(item.get("extension") for item in inventory)

    price_candidates = [
        item for item in inventory
        if item.get("is_price_candidate")
    ]

    output = {
        "generated_at": now_iso(),
        "document_root": str(DOC_ROOT),
        "total_documents": len(inventory),
        "price_candidate_documents": len(price_candidates),
        "document_type_counts": dict(type_counts),
        "extension_counts": dict(ext_counts),
        "price_candidates": price_candidates,
        "documents": inventory,
    }

    write_json(OUTPUT_FILE, output)

    print(f"Document type inventory written: {OUTPUT_FILE}")
    print(f"Total documents: {len(inventory)}")
    print(f"Price candidates: {len(price_candidates)}")
    print("Document type counts:")
    for k, v in type_counts.most_common():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
