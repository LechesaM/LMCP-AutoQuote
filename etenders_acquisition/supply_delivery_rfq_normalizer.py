#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
INPUT_FILE = RUNTIME_DIR / "portal_fetch" / "logs" / "actionable_snapshot_parse.json"
OUTPUT_FILE = RUNTIME_DIR / "portal_fetch" / "logs" / "supply_delivery_rfqs.json"

ACCEPT_KEYWORDS = [
    "supply and delivery",
    "supply & delivery",
    "supply, delivery",
    "supply",
    "deliver",
    "delivery",
    "stationery",
    "pre-printed stationery",
    "ppe",
    "protective clothing",
    "cleaning materials",
    "cleaning material",
    "office furniture",
    "furniture",
    "equipment",
    "tools",
    "consumables",
    "chemicals",
    "spares",
    "cartridges",
    "toners",
    "paper",
    "uniform",
    "uniforms",
    "materials",
    "water meters",
    "guard houses",
    "first aid",
]

REJECT_KEYWORDS = [
    "construction",
    "contractor",
    "contractors",
    "cidb",
    "civil works",
    "building works",
    "turnkey",
    "professional services",
    "consulting",
    "consultancy",
    "panel of contractors",
    "maintenance",
    "repairs",
    "installation",
    "alterations",
    "infrastructure",
    "employer's representative",
    "employers representative",
    "cleaning contract",
    "security services",
    "training",
    "valuation",
    "valuer",
    "medical services",
    "flight",
    "accommodation",
    "car rental",
    "database management",
    "software development",
    "application management",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


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


def clean(value):
    value = str(value or "")
    value = value.replace("&#x27;", "'")
    value = value.replace("&amp;", "&")
    value = value.replace("&#xD;", " ")
    value = value.replace("&#xA;", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def contains_any(text, keywords):
    lower = text.lower()
    return [k for k in keywords if k in lower]


def parse_row(row_text):
    parts = [clean(x) for x in row_text.split("|")]
    parts = [p for p in parts if p]

    if len(parts) >= 5:
        return {
            "department": parts[0],
            "description": parts[1],
            "advert_date": parts[2],
            "closing_date": parts[3],
            "award_date": parts[4],
            "raw_parts": parts,
        }

    return {
        "department": parts[0] if len(parts) > 0 else "",
        "description": parts[1] if len(parts) > 1 else row_text,
        "advert_date": "",
        "closing_date": "",
        "award_date": "",
        "raw_parts": parts,
    }


def classify_supply_delivery(record):
    text_blob = clean(
        f"{record.get('department', '')} {record.get('description', '')}"
    )

    accepts = contains_any(text_blob, ACCEPT_KEYWORDS)
    rejects = contains_any(text_blob, REJECT_KEYWORDS)

    score = 0

    score += len(accepts) * 10
    score -= len(rejects) * 15

    description = record.get("description", "").lower()

    if description.startswith("supply"):
        score += 20

    if "supply and delivery" in description:
        score += 30

    if "cidb" in description:
        score -= 50

    if "contractor" in description or "construction" in description:
        score -= 40

    if "panel of contractors" in description:
        score -= 50

    if score >= 20 and accepts and not any(
        hard in description
        for hard in ["cidb", "construction", "panel of contractors", "turnkey contractor"]
    ):
        decision = "ACCEPT_SUPPLY_DELIVERY"
    elif accepts and rejects:
        decision = "REVIEW_MIXED"
    else:
        decision = "REJECT_NOT_SUPPLY_DELIVERY"

    return {
        "decision": decision,
        "score": score,
        "accept_matches": accepts,
        "reject_matches": rejects,
    }


def make_rfq_id(record, index):
    base = f"{record.get('department','')}-{record.get('description','')[:50]}-{index}"
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-")
    return f"SDRFQ-{base[:80]}"


def main():
    data = load_json(INPUT_FILE, default={})

    accepted = []
    review = []
    rejected = []

    all_rows = []

    for snapshot in data.get("snapshots", []):
        source_snapshot = snapshot.get("snapshot")

        for row in snapshot.get("tender_rows", []):
            row_text = clean(row.get("text", ""))

            if not row_text:
                continue

            if row_text.lower().startswith("department | description"):
                continue

            record = parse_row(row_text)
            classification = classify_supply_delivery(record)

            normalized = {
                "rfq_id": make_rfq_id(record, len(all_rows) + 1),
                "source_snapshot": source_snapshot,
                "department": record["department"],
                "description": record["description"],
                "advert_date": record["advert_date"],
                "closing_date": record["closing_date"],
                "award_date": record["award_date"],
                "classification": classification,
                "raw_row": row_text,
            }

            all_rows.append(normalized)

            if classification["decision"] == "ACCEPT_SUPPLY_DELIVERY":
                accepted.append(normalized)
            elif classification["decision"] == "REVIEW_MIXED":
                review.append(normalized)
            else:
                rejected.append(normalized)

    output = {
        "generated_at": now_iso(),
        "input_file": str(INPUT_FILE),
        "total_rows_seen": len(all_rows),
        "accepted_supply_delivery": len(accepted),
        "review_mixed": len(review),
        "rejected_not_supply_delivery": len(rejected),
        "accepted": accepted,
        "review": review,
        "rejected_sample": rejected[:100],
    }

    write_json(OUTPUT_FILE, output)

    print(f"Supply & Delivery RFQ normalizer output: {OUTPUT_FILE}")
    print(f"Total rows seen: {len(all_rows)}")
    print(f"Accepted supply/delivery: {len(accepted)}")
    print(f"Review mixed: {len(review)}")
    print(f"Rejected: {len(rejected)}")

    print("\nTop accepted:")
    for item in accepted[:20]:
        print(
            f"- {item['department']} | "
            f"{item['description'][:120]} | "
            f"score={item['classification']['score']}"
        )


if __name__ == "__main__":
    main()
