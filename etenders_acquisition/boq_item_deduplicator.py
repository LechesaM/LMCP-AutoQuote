#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "boq_intelligence" / "sanitized_boq_items.json"
OUT_DIR = RUNTIME_DIR / "boq_intelligence"

OUTPUT_FILE = OUT_DIR / "deduplicated_boq_items.json"
SUMMARY_FILE = OUT_DIR / "deduplicated_boq_summary.json"


CODE_ONLY_PATTERN = re.compile(r"^[A-Z0-9\-_/ .]{3,20}$", re.I)
HAS_ALPHA_PATTERN = re.compile(r"[A-Za-z]")
HAS_LONG_WORD_PATTERN = re.compile(r"[A-Za-z]{4,}")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean(value):
    value = "" if value is None else str(value)
    value = value.replace("\n", " ").replace("\r", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_description(value):
    value = clean(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalized_key(item):
    desc = normalize_description(item.get("description"))
    unit = clean(item.get("unit")).lower()
    category = clean(item.get("category")).lower()

    return f"{category}|{unit}|{desc}"


def is_code_only(description):
    d = clean(description)

    if not d:
        return True

    if len(d) < 4:
        return True

    if d.isdigit():
        return True

    if CODE_ONLY_PATTERN.match(d) and not HAS_LONG_WORD_PATTERN.search(d):
        return True

    # Examples: 0681238, A12345, 240-12248652
    digits = sum(ch.isdigit() for ch in d)
    letters = sum(ch.isalpha() for ch in d)

    if digits >= 4 and letters <= 2 and len(d) <= 20:
        return True

    return False


def confidence_adjustment(item):
    flags = list(item.get("sanity_flags") or [])
    score = int(item.get("quality_score") or 0)

    description = clean(item.get("description"))

    if is_code_only(description):
        flags.append("code_only_description")
        score -= 25

    if len(description) < 10:
        flags.append("short_description")
        score -= 10

    if not item.get("unit"):
        flags.append("missing_unit")
        score -= 5

    if item.get("quantity") is None:
        flags.append("missing_quantity")
        score -= 20

    if score >= 50:
        confidence = "HIGH"
    elif score >= 30:
        confidence = "MEDIUM"
    elif score >= 15:
        confidence = "LOW"
    else:
        confidence = "REVIEW"

    return confidence, score, sorted(set(flags))


def make_group_id(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def main():
    data = load_json(INPUT_FILE, default={})
    items = data.get("items", [])

    grouped = defaultdict(list)

    for item in items:
        if item.get("sanity_status") != "USABLE":
            continue

        grouped[normalized_key(item)].append(item)

    deduped = []
    duplicate_groups = []

    for key, group in grouped.items():
        group_id = make_group_id(key)

        # Prefer higher quality, longer description, and with quantity
        group_sorted = sorted(
            group,
            key=lambda x: (
                x.get("quality_score") or 0,
                len(clean(x.get("description"))),
                1 if x.get("quantity") is not None else 0,
            ),
            reverse=True,
        )

        primary = dict(group_sorted[0])
        confidence, adjusted_score, flags = confidence_adjustment(primary)

        quantities = [
            g.get("quantity")
            for g in group
            if g.get("quantity") is not None
        ]

        primary["dedupe_group_id"] = group_id
        primary["duplicate_count"] = len(group)
        primary["dedupe_key"] = key
        primary["aggregate_quantity"] = sum(quantities) if quantities else primary.get("quantity")
        primary["confidence"] = confidence
        primary["confidence_score"] = adjusted_score
        primary["final_flags"] = flags

        primary["duplicate_sources"] = [
            {
                "item_id": g.get("item_id"),
                "quantity": g.get("quantity"),
                "source": g.get("source"),
            }
            for g in group_sorted[:25]
        ]

        deduped.append(primary)

        if len(group) > 1:
            duplicate_groups.append({
                "dedupe_group_id": group_id,
                "duplicate_count": len(group),
                "description": primary.get("description"),
                "unit": primary.get("unit"),
                "category": primary.get("category"),
                "aggregate_quantity": primary.get("aggregate_quantity"),
            })

    review_items = [
        item for item in deduped
        if item.get("confidence") == "REVIEW"
    ]

    usable_for_pricing = [
        item for item in deduped
        if item.get("confidence") in ["HIGH", "MEDIUM"]
    ]

    confidence_counts = Counter(i.get("confidence") for i in deduped)
    category_counts = Counter(i.get("category") for i in deduped)
    duplicate_count_distribution = Counter(i.get("duplicate_count") for i in deduped)

    output = {
        "generated_at": now_iso(),
        "input_usable_items": sum(1 for i in items if i.get("sanity_status") == "USABLE"),
        "deduplicated_items": len(deduped),
        "usable_for_pricing": len(usable_for_pricing),
        "review_items": len(review_items),
        "duplicate_groups": len(duplicate_groups),
        "confidence_counts": dict(confidence_counts),
        "category_counts": dict(category_counts),
        "duplicate_count_distribution": dict(duplicate_count_distribution),
        "items": deduped,
        "usable_pricing_items": usable_for_pricing,
        "review_sample": review_items[:1000],
        "duplicate_group_sample": duplicate_groups[:1000],
    }

    summary = {
        "generated_at": output["generated_at"],
        "input_usable_items": output["input_usable_items"],
        "deduplicated_items": output["deduplicated_items"],
        "usable_for_pricing": output["usable_for_pricing"],
        "review_items": output["review_items"],
        "duplicate_groups": output["duplicate_groups"],
        "confidence_counts": output["confidence_counts"],
        "category_counts": output["category_counts"],
        "duplicate_count_distribution_top_20": dict(duplicate_count_distribution.most_common(20)),
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Deduplicated BOQ items written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Input usable items: {output['input_usable_items']}")
    print(f"Deduplicated items: {output['deduplicated_items']}")
    print(f"Usable for pricing: {output['usable_for_pricing']}")
    print(f"Review items: {output['review_items']}")
    print(f"Duplicate groups: {output['duplicate_groups']}")


if __name__ == "__main__":
    main()
