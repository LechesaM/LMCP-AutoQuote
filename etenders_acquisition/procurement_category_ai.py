#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "final_bid_pricing" / "final_bid_pricing_schedule.json"

OUT_DIR = RUNTIME_DIR / "procurement_category_ai"

OUTPUT_FILE = OUT_DIR / "recategorized_pricing_schedule.json"
SUMMARY_FILE = OUT_DIR / "procurement_category_ai_summary.json"


CATEGORY_RULES = {
    "mechanical": {
        "high": [
            "bearing", "ball bearing", "roller bearing", "thrust bearing",
            "skf", "fag", "nsk", "timken", "plummer block",
            "coupling", "pulley", "shaft", "bush", "bushing",
            "gasket", "seal", "sleeve", "gearbox", "pump", "valve",
            "taper lock", "fenaflex", "nupex", "conveyor"
        ],
        "medium": [
            "inside diameter", "outside diameter", "bore diameter",
            "row single", "row double", "style open", "cage material",
            "material stl", "grease", "lubricant"
        ],
    },
    "electrical": {
        "high": [
            "cable", "transformer", "voltage", "mcb", "breaker",
            "switch", "panel", "abb", "siemens", "schneider",
            "contactor", "relay", "battery", "charger", "light fitting"
        ],
        "medium": [
            "volt", "amp", "kw", "electrical", "wiring", "terminal"
        ],
    },
    "stationery": {
        "high": [
            "pen", "paper", "pencil", "file", "lever arch",
            "stapler", "staples", "notebook", "counter book",
            "clip", "folder", "envelope", "binder", "typek"
        ],
        "medium": [
            "a4", "a3", "ream", "stationery", "whiteboard marker"
        ],
    },
    "ppe": {
        "high": [
            "helmet", "glove", "overall", "boot", "safety shoe",
            "protective clothing", "ppe", "respirator", "mask",
            "goggles", "hard hat", "reflective"
        ],
        "medium": [
            "safety", "high visibility", "protective"
        ],
    },
    "building_material": {
        "high": [
            "cement", "concrete", "brick", "slab", "sand", "stone",
            "aggregate", "timber", "paint", "bitumen", "asphalt",
            "prime coat", "tack coat", "pipe", "kerb", "channel"
        ],
        "medium": [
            "m2", "m3", "litre", "surfacing", "road", "civil"
        ],
    },
    "ict": {
        "high": [
            "laptop", "computer", "server", "printer", "scanner",
            "router", "switch network", "cat6", "ethernet", "monitor",
            "tablet", "software", "license"
        ],
        "medium": [
            "usb", "wifi", "wi-fi", "network", "android"
        ],
    },
    "furniture": {
        "high": [
            "chair", "desk", "table", "cabinet", "shelf", "wardrobe",
            "office furniture"
        ],
        "medium": [
            "drawer", "seat", "workstation"
        ],
    },
    "cleaning": {
        "high": [
            "soap", "detergent", "disinfectant", "cleaning",
            "mop", "broom", "toilet paper", "sanitizer"
        ],
        "medium": [
            "hygiene", "chemical"
        ],
    },
    "medical": {
        "high": [
            "medical", "clinic", "syringe", "first aid",
            "hospital", "bandage", "stretcher"
        ],
        "medium": [
            "health", "patient"
        ],
    },
}


SKU_MECHANICAL_PATTERNS = [
    r"\b\d{4,5}[- ]?(2RS|ZZ|C3|C4|K|NR|Z)\b",
    r"\bNU\d{3,5}[A-Z0-9]*\b",
    r"\bNJ\d{3,5}[A-Z0-9]*\b",
    r"\bNUP\d{3,5}[A-Z0-9]*\b",
    r"\bRLS\d+\b",
    r"\bALS\d+\b",
    r"\bQJM\d+\b",
    r"\bTSNA\d+[A-Z]?\b",
    r"\bAHX?\d+\b",
    r"\bHE\d+\b",
]


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


def normalize(text):
    text = str(text or "").lower()
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def phrase_match(text, phrase):
    t = normalize(text)
    p = normalize(phrase)
    if not t or not p:
        return False
    return bool(re.search(r"\b" + re.escape(p) + r"\b", t))


def sku_mechanical_score(description):
    upper = str(description or "").upper()
    score = 0
    hits = []

    for pattern in SKU_MECHANICAL_PATTERNS:
        if re.search(pattern, upper):
            score += 25
            hits.append(pattern)

    return score, hits


def score_category(description):
    scores = Counter()
    evidence = {}

    for category, groups in CATEGORY_RULES.items():
        evidence[category] = []

        for phrase in groups.get("high", []):
            if phrase_match(description, phrase):
                scores[category] += 25
                evidence[category].append(f"high:{phrase}")

        for phrase in groups.get("medium", []):
            if phrase_match(description, phrase):
                scores[category] += 10
                evidence[category].append(f"medium:{phrase}")

    sku_score, sku_hits = sku_mechanical_score(description)

    if sku_score:
        scores["mechanical"] += sku_score
        evidence.setdefault("mechanical", []).extend([f"sku:{x}" for x in sku_hits])

    if not scores:
        return "general_supply", 0, []

    best_category, best_score = scores.most_common(1)[0]

    return best_category, best_score, evidence.get(best_category, [])


def recategorize_line(line):
    description = line.get("description")
    old_category = line.get("category")

    new_category, score, evidence = score_category(description)

    out = dict(line)
    out["old_category"] = old_category
    out["category"] = new_category
    out["category_ai_score"] = score
    out["category_ai_evidence"] = evidence
    out["category_changed"] = old_category != new_category

    return out


def main():
    data = load_json(INPUT_FILE, default={})
    lines = data.get("pricing_schedule", [])

    recategorized = [recategorize_line(line) for line in lines]

    changed = [x for x in recategorized if x.get("category_changed")]

    old_counts = Counter(line.get("category") or "unknown" for line in lines)
    new_counts = Counter(line.get("category") or "unknown" for line in recategorized)

    summary = {
        "generated_at": now_iso(),
        "input_lines": len(lines),
        "changed_categories": len(changed),
        "old_category_counts": dict(old_counts),
        "new_category_counts": dict(new_counts),
        "top_changes": Counter(
            f"{x.get('old_category')} -> {x.get('category')}"
            for x in changed
        ).most_common(30),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "pricing_schedule": recategorized,
        "changed_sample": changed[:500],
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Recategorized pricing schedule written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Input lines: {summary['input_lines']}")
    print(f"Changed categories: {summary['changed_categories']}")

    print("\nTop changes:")
    for change, count in summary["top_changes"]:
        print(f"- {change}: {count}")


if __name__ == "__main__":
    main()
