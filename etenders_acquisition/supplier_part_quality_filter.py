#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "supplier_expansion"
    / "manufacturer_part_index.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_expansion"

OUTPUT_FILE = OUT_DIR / "filtered_manufacturer_part_index.json"
SUMMARY_FILE = OUT_DIR / "part_quality_filter_summary.json"


DIMENSION_PATTERNS = [
    r"^\d+(\.\d+)?MM$",
    r"^\d+(\.\d+)?CM$",
    r"^\d+(\.\d+)?M$",
    r"^\d+(\.\d+)?IN$",
    r"^\d+(\.\d+)?X\d+(\.\d+)?(MM|CM|M|IN)?$",
    r"^\d+(\.\d+)?MMX\d+(\.\d+)?MM$",
]

POWER_PATTERNS = [
    r"^\d+(\.\d+)?V$",
    r"^\d+(\.\d+)?VOLT$",
    r"^\d+(\.\d+)?W$",
    r"^\d+(\.\d+)?KW$",
    r"^\d+(\.\d+)?WATT$",
    r"^\d+(\.\d+)?AMP$",
]

NOISE_TERMS = {
    "NON-FERROUS",
    "SUB-STRUCTURES",
    "PRE-TENSIONING",
    "V-SHAPED",
    "SELF-CENTERING",
    "QUAD-CORE",
    "LITHIUM-ION",
    "TYPE-A",
    "TYPE-C",
    "WI-FI",
    "ISO40",
}

MATERIAL_TERMS = {
    "STL",
    "CS",
    "CI",
    "SS",
    "RUBBER",
    "POLYMER",
    "BRASS",
    "ALUMINUM",
    "ALUMINIUM",
}

KNOWN_OEM_PREFIXES = [
    "SKF",
    "FAG",
    "NSK",
    "TIMKEN",
    "ABB",
    "SIEMENS",
    "SCHNEIDER",
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


def classify_part(part):
    p = str(part or "").strip().upper()

    if not p:
        return "noise"

    if p in NOISE_TERMS:
        return "noise"

    if p in MATERIAL_TERMS:
        return "material"

    for pattern in DIMENSION_PATTERNS:
        if re.match(pattern, p):
            return "technical_spec_dimension"

    for pattern in POWER_PATTERNS:
        if re.match(pattern, p):
            return "technical_spec_power"

    if re.match(r"^\d+(\.\d+)?L$", p):
        return "technical_spec_capacity"

    if re.match(r"^\d+(\.\d+)?KG$", p):
        return "technical_spec_weight"

    if re.match(r"^\d+$", p):
        return "numeric_code_review"

    if any(p.startswith(prefix) for prefix in KNOWN_OEM_PREFIXES):
        return "true_part_number"

    if re.search(r"[A-Z]", p) and re.search(r"\d", p):
        if len(p) >= 5:
            return "true_part_number"

    if "-" in p or "/" in p:
        if re.search(r"\d", p):
            return "true_part_number"

    return "noise"


def main():
    data = load_json(INPUT_FILE, default={})
    part_index = data.get("manufacturer_part_index", {})

    buckets = defaultdict(dict)

    for part, records in part_index.items():
        cls = classify_part(part)
        buckets[cls][part] = records

    filtered = {
        "generated_at": now_iso(),
        "true_part_numbers": buckets.get("true_part_number", {}),
        "numeric_code_review": buckets.get("numeric_code_review", {}),
        "technical_specs": {
            "dimensions": buckets.get("technical_spec_dimension", {}),
            "power": buckets.get("technical_spec_power", {}),
            "capacity": buckets.get("technical_spec_capacity", {}),
            "weight": buckets.get("technical_spec_weight", {}),
        },
        "materials": buckets.get("material", {}),
        "noise": buckets.get("noise", {}),
    }

    summary = {
        "generated_at": filtered["generated_at"],
        "input_parts": len(part_index),
        "true_part_numbers": len(filtered["true_part_numbers"]),
        "numeric_code_review": len(filtered["numeric_code_review"]),
        "technical_dimensions": len(filtered["technical_specs"]["dimensions"]),
        "technical_power": len(filtered["technical_specs"]["power"]),
        "technical_capacity": len(filtered["technical_specs"]["capacity"]),
        "technical_weight": len(filtered["technical_specs"]["weight"]),
        "materials": len(filtered["materials"]),
        "noise": len(filtered["noise"]),
        "classification_counts": {
            k: len(v) for k, v in buckets.items()
        },
    }

    write_json(OUTPUT_FILE, filtered)
    write_json(SUMMARY_FILE, summary)

    print(f"Filtered part index written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Input parts: {summary['input_parts']}")
    print(f"True part numbers: {summary['true_part_numbers']}")
    print(f"Technical dimensions: {summary['technical_dimensions']}")
    print(f"Technical power: {summary['technical_power']}")
    print(f"Noise: {summary['noise']}")


if __name__ == "__main__":
    main()
